"""wocli sys - Show system status with animated bars."""

import os
import platform
import re
import shutil
import sys
import time

from wocli import terminal
from wocli.utils import format_bytes, render_bar, run_cmd

# Linux 的 CPU 占用要靠 /proc/stat 前后两次采样的差值，这里存上一次的读数
_CPU_SAMPLE = {"total": None, "idle": None}


def _to_int(text):
    """从任意文本里取第一个整数，兼容 vm_stat 的 "8908." 和带千分位的写法."""
    digits = re.sub(r"[^\d]", "", str(text))
    if not digits:
        return None
    return int(digits)


def _first_float(text):
    match = re.search(r"-?\d+(?:\.\d+)?", text or "")
    return float(match.group(0)) if match else None


# ---------- CPU ----------

def _cpu_from_proc_stat():
    """读 /proc/stat 第一行 cpu 的累计 jiffies，返回 (总时间, 空闲时间)."""
    try:
        with open("/proc/stat", "r") as handle:
            fields = handle.readline().split()
    except OSError:
        return None
    if len(fields) < 5 or fields[0] != "cpu":
        return None
    try:
        values = [int(value) for value in fields[1:]]
    except ValueError:
        return None
    # idle 是第 4 项、iowait 是第 5 项，等待 IO 也算没在干活
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return sum(values), idle


def _cpu_usage_linux():
    """用两次 /proc/stat 的差值算占用率.

    只读一次拿到的是开机以来的平均值——这不是"当前占用"，
    而且顺带绕开了精简容器里没有 top 的问题。
    """
    sample = _cpu_from_proc_stat()
    if sample is None:
        return None
    previous = (_CPU_SAMPLE["total"], _CPU_SAMPLE["idle"])
    _CPU_SAMPLE["total"], _CPU_SAMPLE["idle"] = sample
    if previous[0] is None:
        # 第一次调用没有参照点，睡一小会儿再采一次
        time.sleep(0.3)
        sample = _cpu_from_proc_stat()
        if sample is None:
            return None
        previous = (_CPU_SAMPLE["total"], _CPU_SAMPLE["idle"])
        _CPU_SAMPLE["total"], _CPU_SAMPLE["idle"] = sample

    total_delta = sample[0] - previous[0]
    idle_delta = sample[1] - previous[1]
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def _cpu_usage_macos():
    """取 top 第二份采样的 CPU 占用：第一份会系统性偏高 7~10 个百分点.

    实测对照（本机 10 核，8 个进程压满 vs 空载，同时用独立的 iostat -c 2 做参照）：
      空载   iostat 区间值 12.0% | top 第一份 18.9%（sys 占比明显偏大）| top 第二份 11.7%
      满载   iostat 区间值 84.0% | top 第一份 94.0%                     | top 第二份 84.5%
    第二份和 iostat 基本一致，所以只取第二份；用 100 - idle 比 user + sys 更全。
    """
    text = run_cmd(["top", "-l", "2", "-n", "0"], timeout=20)
    matches = re.findall(
        r"CPU usage:\s*[\d.]+%\s*user,\s*[\d.]+%\s*sys,\s*([\d.]+)%\s*idle", text or ""
    )
    if not matches:
        return None
    idle = float(matches[-1])
    return max(0.0, min(100.0, 100.0 - idle))


def _cpu_usage_windows():
    out = run_cmd([
        "powershell", "-NoProfile", "-Command",
        "(Get-CimInstance Win32_Processor | "
        "Measure-Object -Property LoadPercentage -Average).Average",
    ], timeout=15)
    value = _first_float(out)
    if value is None:
        # 部分机型 LoadPercentage 是空的，退到性能计数器（类名不随系统语言变）
        out = run_cmd([
            "powershell", "-NoProfile", "-Command",
            "(Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor | "
            "Where-Object { $_.Name -eq '_Total' }).PercentProcessorTime",
        ], timeout=15)
        value = _first_float(out)
    if value is None or not 0 <= value <= 100:
        return None
    return value


def get_cpu_usage():
    """返回当前 CPU 占用百分比；取不到返回 None，不用 0 假装."""
    system = platform.system()
    if system == "Darwin":
        return _cpu_usage_macos()
    if system == "Windows":
        return _cpu_usage_windows()
    return _cpu_usage_linux()


# ---------- 内存 ----------

def _memory_macos():
    """vm_stat 的 active + wired + 压缩页才是"已用"内存.

    旧实现漏了 "Pages occupied by compressor"：Apple Silicon 上压缩页能占好几个 GB，
    漏算会把 77% 的占用显示成 60%。
    """
    text = run_cmd(["vm_stat"], timeout=8)
    if not text:
        return None, None

    page_size = 4096
    match = re.search(r"page size of (\d+) bytes", text)
    if match:
        page_size = int(match.group(1))

    pages = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        pages[key.strip()] = _to_int(value)
    used_pages = (
        (pages.get("Pages active") or 0)
        + (pages.get("Pages wired down") or 0)
        + (pages.get("Pages occupied by compressor") or 0)
    )
    if used_pages <= 0:
        return None, None

    total = _to_int(run_cmd(["sysctl", "-n", "hw.memsize"], timeout=5))
    if not total:
        try:
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError, AttributeError):
            total = None
    if not total:
        return None, None
    return min(used_pages * page_size, total), total


def _memory_linux():
    try:
        with open("/proc/meminfo", "r") as handle:
            rows = handle.read().splitlines()
    except OSError:
        return None, None

    values = {}
    for row in rows:
        if ":" not in row:
            continue
        key, _, rest = row.partition(":")
        amount = _to_int(rest)
        if amount is not None:
            values[key.strip()] = amount * 1024  # meminfo 的单位是 kB
    total = values.get("MemTotal")
    if not total:
        return None, None
    available = values.get("MemAvailable")
    if available is None:
        # 3.14 之前的内核没有 MemAvailable，用 free + buffers + cached 近似
        available = (
            values.get("MemFree", 0)
            + values.get("Buffers", 0)
            + values.get("Cached", 0)
        )
    return max(0, total - available), total


def _memory_windows():
    out = run_cmd([
        "powershell", "-NoProfile", "-Command",
        "$os = Get-CimInstance Win32_OperatingSystem; "
        "'{0} {1}' -f $os.TotalVisibleMemorySize, $os.FreePhysicalMemory",
    ], timeout=15)
    parts = (out or "").split()
    if len(parts) < 2:
        return None, None
    total = _to_int(parts[0])
    free = _to_int(parts[1])
    if not total or free is None:
        return None, None
    return max(0, total - free) * 1024, total * 1024


def get_memory_usage():
    """返回 (已用, 总量) 字节数，取不到给 (None, None)."""
    system = platform.system()
    if system == "Darwin":
        return _memory_macos()
    if system == "Windows":
        return _memory_windows()
    return _memory_linux()


# ---------- 磁盘 ----------

def get_disk_usage():
    """shutil.disk_usage 三个平台都能用（os.statvfs 在 Windows 上不存在）."""
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
    except OSError:
        return None, None
    return usage.used, usage.total


# ---------- 输出 ----------

def _pad_label(label, width=6):
    """按终端显示宽度补齐标签：中文占两列，不这么补「CPU」和「内存」的方括号会错开."""
    shown = sum(2 if ord(char) > 0x2E80 else 1 for char in label)
    return label + " " * max(0, width - shown)


def draw_bar(label, used, total, width=30):
    """画一行 [bar] 已用/总量；取不到数据就写「未获取到」，不印一个假的 0%."""
    if not used or not total:
        return f"  {_pad_label(label)} 未获取到"
    return (f"  {_pad_label(label)} [{render_bar(used / total, width)}] "
            f"{format_bytes(used)} / {format_bytes(total)}")


def draw_cpu(cpu, width=30):
    if cpu is None:
        return f"  {_pad_label('CPU')} 未获取到"
    return f"  {_pad_label('CPU')} [{render_bar(cpu / 100, width)}] {cpu:.0f}%"


def run():
    print(f"\n  系统状态 · {platform.system()} {platform.release()}")
    print()

    for index in range(3):
        started = time.monotonic()
        cpu = get_cpu_usage()
        mem_used, mem_total = get_memory_usage()
        disk_used, disk_total = get_disk_usage()

        # \033[K 清行尾，防止上一轮的长数字残留
        print(draw_cpu(cpu) + "\033[K")
        print(draw_bar("内存", mem_used, mem_total) + "\033[K")
        print(draw_bar("磁盘", disk_used, disk_total) + "\033[K")

        if index < 2:
            # 采样本身就要时间（macOS 的 top -l 2 约一秒），只补足剩下的间隔
            time.sleep(max(0.0, 1.0 - (time.monotonic() - started)))
            if terminal.CAPS["ansi"]:
                sys.stdout.write("\033[3A")  # 上移三行覆盖重绘
                sys.stdout.flush()

    print()
