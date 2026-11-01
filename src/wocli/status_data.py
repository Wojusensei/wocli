"""驾驶舱 TUI 的系统数据采集.

所有公开读取函数都遵循同一个约定：拿不到就返回 None 或空分类，
绝不抛异常，也绝不编一个 0 出来假装正常。慢命令（macOS 的 top /
system_profiler、Windows 的 powercfg）由 StatusCollector 放到后台线程，
状态栏只读缓存，不会被采集卡住。
"""

import os
import platform
import re
import shutil
import threading
import time
from dataclasses import dataclass, replace
from typing import Optional, Sequence, Tuple

from wocli import __version__
from wocli.commands import battery, sys_cmd, wifi_cmd
from wocli.utils import run_cmd


# ---------- 数据结构 ----------

@dataclass(frozen=True)
class MemoryCategory:
    key: str
    label: str
    bytes: int


@dataclass(frozen=True)
class MemoryInfo:
    total: int
    used: int
    categories: Tuple[MemoryCategory, ...]


@dataclass(frozen=True)
class CpuInfo:
    percent: Optional[float]
    cores: int
    load: Optional[Tuple[float, float, float]]


@dataclass(frozen=True)
class DiskInfo:
    used: int
    total: int


@dataclass(frozen=True)
class BatteryInfo:
    percent: int
    status: str
    cycles: Optional[int]
    health: Optional[int]
    temp: Optional[float]


@dataclass(frozen=True)
class WifiInfo:
    ssid: Optional[str]
    rssi: Optional[int]
    channel: Optional[str]
    rate: Optional[str]
    note: Optional[str]


@dataclass(frozen=True)
class GitInfo:
    branch: str
    dirty: bool
    additions: int
    deletions: int
    untracked: int


@dataclass(frozen=True)
class SystemInfo:
    os_name: str
    os_release: str
    machine: str
    cores: int
    python: str
    os_label: str = ""


@dataclass(frozen=True)
class StatusSnapshot:
    version: str
    cwd: str
    system: SystemInfo
    cpu: Optional[CpuInfo] = None
    memory: Optional[MemoryInfo] = None
    disk: Optional[DiskInfo] = None
    battery: Optional[BatteryInfo] = None
    wifi: Optional[WifiInfo] = None
    git: Optional[GitInfo] = None
    captured_at: float = 0.0


# ---------- 内存 ----------

def _to_int(text):
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else None


def normalize_memory_categories(
    categories: Sequence[MemoryCategory], total: int
) -> Tuple[MemoryCategory, ...]:
    """把分类强行对齐到 total，保证 waffle 的格子加起来刚好是 100%.

    vm_stat / meminfo 的各项之间偶尔会有几十 MB 的对不上（内核保留页、
    舍入误差），直接画会多出或少掉一格；这里把差额并进"空闲"，
    只有总和超出 total 时才按比例缩回去。
    """
    if total <= 0:
        return tuple(c for c in categories if c.bytes > 0)

    cats = [MemoryCategory(c.key, c.label, max(0, int(c.bytes))) for c in categories]
    cats = [c for c in cats if c.bytes > 0]
    if not cats:
        return (MemoryCategory("free", "空闲", total),)

    summed = sum(c.bytes for c in cats)
    if summed < total:
        diff = total - summed
        free = next((c for c in cats if c.key == "free"), None)
        if free is not None:
            cats = [replace(c, bytes=c.bytes + diff) if c is free else c for c in cats]
        else:
            cats.append(MemoryCategory("other", "其他", diff))
    elif summed > total:
        scale = total / float(summed)
        scaled = [max(0, int(c.bytes * scale)) for c in cats]
        remainder = total - sum(scaled)
        biggest = max(range(len(scaled)), key=lambda i: scaled[i])
        scaled[biggest] += remainder
        cats = [
            MemoryCategory(c.key, c.label, value)
            for c, value in zip(cats, scaled)
            if value > 0
        ]

    return tuple(cats)


def _memory_info_from_categories(
    categories: Sequence[MemoryCategory], total: int
) -> Optional[MemoryInfo]:
    if not total or total <= 0:
        return None
    cats = normalize_memory_categories(categories, total)
    if not cats:
        return None
    free_bytes = sum(c.bytes for c in cats if c.key == "free")
    used = max(0, total - free_bytes) if free_bytes else sum(c.bytes for c in cats)
    return MemoryInfo(total=total, used=min(used, total), categories=cats)


def parse_macos_memory(vm_stat_text: str, total_bytes: Optional[int]) -> Optional[MemoryInfo]:
    """vm_stat 分类：active=应用，inactive+speculative=缓存，wired+压缩=系统."""
    if not vm_stat_text or not total_bytes:
        return None

    page_size = 4096
    match = re.search(r"page size of (\d+) bytes", vm_stat_text)
    if match:
        page_size = int(match.group(1))

    pages = {}
    for line in vm_stat_text.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        amount = _to_int(value)
        if amount is not None:
            pages[key.strip()] = amount

    if not pages:
        return None

    app = (pages.get("Pages active") or 0) * page_size
    cache = (
        (pages.get("Pages inactive") or 0)
        + (pages.get("Pages speculative") or 0)
    ) * page_size
    system = (
        (pages.get("Pages wired down") or 0)
        + (pages.get("Pages occupied by compressor") or 0)
    ) * page_size
    free = max(0, total_bytes - app - cache - system)

    return _memory_info_from_categories(
        [
            MemoryCategory("app", "应用", app),
            MemoryCategory("cache", "缓存", cache),
            MemoryCategory("sys", "系统", system),
            MemoryCategory("free", "空闲", free),
        ],
        total_bytes,
    )


def parse_linux_memory(meminfo_text: str) -> Optional[MemoryInfo]:
    """把 /proc/meminfo 拆成应用 / 缓存 / 内核 / 空闲四类."""
    if not meminfo_text:
        return None

    values = {}
    for line in meminfo_text.splitlines():
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        amount = _to_int(rest)
        if amount is not None:
            values[key.strip()] = amount * 1024

    total = values.get("MemTotal")
    if not total:
        return None

    free = values.get("MemFree", values.get("MemAvailable", 0))
    cache = (
        values.get("Buffers", 0)
        + values.get("Cached", 0)
        + values.get("SReclaimable", 0)
    )
    cache = max(0, cache - values.get("Shmem", 0))
    kernel = max(0, values.get("Slab", 0) - values.get("SReclaimable", 0))
    kernel += values.get("KernelStack", 0)
    app = max(0, total - free - cache - kernel)

    return _memory_info_from_categories(
        [
            MemoryCategory("app", "应用", app),
            MemoryCategory("cache", "缓存", cache),
            MemoryCategory("sys", "系统", kernel),
            MemoryCategory("free", "空闲", free),
        ],
        total,
    )


def parse_windows_memory(text: str) -> Optional[MemoryInfo]:
    """PowerShell 输出：TotalVisibleMemorySize(KB) FreePhysicalMemory(KB) CacheBytes(B)."""
    parts = (text or "").split()
    if len(parts) < 2:
        return None

    total = _to_int(parts[0])
    free = _to_int(parts[1])
    if not total or free is None:
        return None
    total *= 1024
    free *= 1024

    cache = _to_int(parts[2]) if len(parts) >= 3 else 0
    # 个别系统上 CacheBytes 会缺失或者是 0，这时只用已用/空闲两类
    cache = min(cache or 0, max(0, total - free))
    app = max(0, total - free - cache)

    categories = [MemoryCategory("app", "应用", app), MemoryCategory("free", "空闲", free)]
    if cache > 0:
        categories.insert(1, MemoryCategory("cache", "缓存", cache))

    return _memory_info_from_categories(categories, total)


def _memory_from_usage(used: Optional[int], total: Optional[int]) -> Optional[MemoryInfo]:
    if used is None or not total:
        return None
    used = max(0, min(used, total))
    return _memory_info_from_categories(
        [
            MemoryCategory("app", "已用", max(0, used)),
            MemoryCategory("free", "空闲", max(0, total - used)),
        ],
        total,
    )


def read_memory() -> Optional[MemoryInfo]:
    system = platform.system()
    try:
        if system == "Darwin":
            text = run_cmd(["vm_stat"], timeout=8)
            total = _to_int(run_cmd(["sysctl", "-n", "hw.memsize"], timeout=5))
            info = parse_macos_memory(text or "", total)
            if info:
                return info
        elif system == "Windows":
            text = run_cmd([
                "powershell", "-NoProfile", "-Command",
                "$os = Get-CimInstance Win32_OperatingSystem; "
                "$m = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; "
                "'{0} {1} {2}' -f $os.TotalVisibleMemorySize, "
                "$os.FreePhysicalMemory, $m.CacheBytes",
            ], timeout=15)
            info = parse_windows_memory(text or "")
            if info:
                return info
        else:
            try:
                with open("/proc/meminfo", "r") as handle:
                    info = parse_linux_memory(handle.read())
            except OSError:
                info = None
            if info:
                return info
    except Exception:
        pass

    # 分类解析失败时退回 sys 命令的 (已用, 总量)
    try:
        used, total = sys_cmd.get_memory_usage()
    except Exception:
        return None
    return _memory_from_usage(used, total)


# ---------- CPU / 磁盘 ----------

def read_cpu() -> CpuInfo:
    percent = None
    try:
        percent = sys_cmd.get_cpu_usage()
    except Exception:
        percent = None

    load = None
    try:
        raw = os.getloadavg()
        load = (float(raw[0]), float(raw[1]), float(raw[2]))
    except (AttributeError, OSError):
        load = None

    return CpuInfo(percent=percent, cores=os.cpu_count() or 0, load=load)


def read_disk() -> Optional[DiskInfo]:
    try:
        usage = shutil.disk_usage(os.path.expanduser("~"))
    except OSError:
        return None
    if not usage.total:
        return None
    return DiskInfo(used=usage.used, total=usage.total)


# ---------- 电池 / WiFi / Git ----------

def read_battery() -> Optional[BatteryInfo]:
    system = platform.system()
    try:
        if system == "Darwin":
            data = battery.get_battery_macos()
        elif system == "Windows":
            data = battery.get_battery_windows()
        else:
            data = battery.get_battery_linux()
    except Exception:
        return None

    percent, status, cycles, health, temp = data
    if percent is None:
        return None
    return BatteryInfo(
        percent=percent,
        status=status,
        cycles=cycles,
        health=health,
        temp=temp,
    )


def read_wifi() -> Optional[WifiInfo]:
    """复用 wifi 命令的采集器；私有函数在包内共享，避免复制三套平台解析."""
    system = platform.system()
    try:
        if system == "Darwin":
            info = wifi_cmd._macos_wifi()
        elif system == "Windows":
            info = wifi_cmd._windows_wifi()
        else:
            info = wifi_cmd._linux_wifi()
    except Exception:
        return None

    return WifiInfo(
        ssid=info.get("ssid"),
        rssi=info.get("rssi"),
        channel=info.get("channel"),
        rate=info.get("rate"),
        note=info.get("note"),
    )


def _git(cwd: str, *args: str, timeout: float = 3) -> str:
    return (run_cmd(["git", "-C", cwd] + list(args), timeout=timeout) or "").strip()


def parse_git_status(porcelain: str, numstat: str = "") -> Optional[GitInfo]:
    """解析 git status --porcelain=v1 --branch 和 git diff HEAD --numstat."""
    branch = None
    dirty = False
    untracked = 0

    for line in (porcelain or "").splitlines():
        if line.startswith("## "):
            head = line[3:].strip()
            if head.startswith("No commits yet on "):
                branch = head[len("No commits yet on "):].strip()
            else:
                branch = re.split(r"\.\.\.| ", head, maxsplit=1)[0].strip()
            continue
        if line.strip():
            dirty = True
            if line.startswith("??"):
                untracked += 1

    if not branch:
        return None

    additions = 0
    deletions = 0
    for line in (numstat or "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            additions += int(parts[0])
            deletions += int(parts[1])

    return GitInfo(
        branch=branch,
        dirty=dirty,
        additions=additions,
        deletions=deletions,
        untracked=untracked,
    )


def read_git(cwd: Optional[str]) -> Optional[GitInfo]:
    if not cwd:
        return None
    try:
        porcelain = _git(cwd, "status", "--porcelain=v1", "--branch", timeout=4)
        if not porcelain:
            return None
        numstat = _git(cwd, "diff", "HEAD", "--numstat", timeout=4)
        return parse_git_status(porcelain, numstat)
    except Exception:
        return None


def _linux_distro_name() -> str:
    """从 os-release 取发行版名，Ubuntu/Debian/Arch 都能读出一个像样的标签."""
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, "r") as handle:
                data = {}
                for line in handle:
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    data[key.strip()] = value.strip().strip('"')
        except OSError:
            continue

        pretty = data.get("PRETTY_NAME") or data.get("NAME")
        version = data.get("VERSION_ID") or data.get("VERSION")
        if pretty and version and version not in pretty:
            return "%s %s" % (pretty, version)
        if pretty:
            return pretty
    return ""


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version", "r") as handle:
            return "microsoft" in handle.read().lower()
    except OSError:
        return False


def friendly_os_label(
    system: str,
    release: str,
    version: str,
    mac_version: str = "",
    distro: str = "",
    wsl: bool = False,
    wsl_distro: str = "",
) -> str:
    """把 platform 的三元组翻成人看的系统名.

    直接显示 platform.release() 会出现 "Darwin 27.0.0"、"Windows 10"
    （哪怕机器是 Win11）这种对用户没意义的标签。
    """
    system = system or "Unknown"
    release = (release or "").strip()
    version = (version or "").strip()

    if system == "Darwin":
        return "macOS %s" % ((mac_version or release).strip() or "?")

    if system == "Windows":
        build = 0
        tail = version.rsplit(".", 1)[-1] if version else ""
        if tail.isdigit():
            build = int(tail)
        if build >= 22000:
            name = "Windows 11"
        elif build >= 10240:
            name = "Windows 10"
        else:
            name = ("Windows %s" % release).strip() if release else "Windows"
        return "%s (%d)" % (name, build) if build else name

    if system == "Linux":
        if wsl:
            base = wsl_distro or distro or (("Linux %s" % release).strip())
            return "WSL · %s" % base
        return distro or (("Linux %s" % release).strip() or "Linux")

    return ("%s %s" % (system, release)).strip() or system


def read_system() -> SystemInfo:
    system = platform.system()
    release = platform.release()
    version = platform.version()
    mac_version = platform.mac_ver()[0] if system == "Darwin" else ""
    distro = _linux_distro_name() if system == "Linux" else ""
    wsl = system == "Linux" and _is_wsl()
    wsl_distro = os.environ.get("WSL_DISTRO_NAME", "") if wsl else ""

    return SystemInfo(
        os_name=system,
        os_release=release,
        machine=platform.machine(),
        cores=os.cpu_count() or 0,
        python=platform.python_version(),
        os_label=friendly_os_label(
            system,
            release,
            version,
            mac_version=mac_version,
            distro=distro,
            wsl=wsl,
            wsl_distro=wsl_distro,
        ),
    )


# ---------- 首次快照与后台刷新 ----------

def initial_snapshot(cwd: str) -> StatusSnapshot:
    """同步采集启动时就该看见的东西；CPU/电池/WiFi 留给后台线程."""
    return StatusSnapshot(
        version=__version__,
        cwd=cwd,
        system=read_system(),
        memory=read_memory(),
        disk=read_disk(),
        git=read_git(cwd),
        captured_at=time.time(),
    )


class StatusCollector:
    """后台多线程采集器.

    每类数据一个线程，慢的（macOS 的 top、system_profiler）不会把
    CPU/内存刷新一起拖住。状态栏只读不可变快照，采集失败保留上一帧。
    """

    def __init__(self, cwd: str):
        self._cwd = cwd
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._snapshot = initial_snapshot(cwd)
        self._threads = []
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        system = platform.system()
        cpu_interval = 5.0 if system == "Darwin" else 2.5
        battery_interval = 60.0 if system == "Windows" else 15.0

        specs = [
            # key, reader, interval, initial delay, keep last value on failure
            ("cpu", read_cpu, cpu_interval, 0.5, True),
            ("memory", read_memory, 2.5, 2.0, True),
            ("disk", read_disk, 8.0, 5.0, True),
            ("git", lambda: read_git(self._cwd), 3.0, 3.0, True),
            ("battery", read_battery, battery_interval, 2.0, False),
            ("wifi", read_wifi, 30.0, 1.5, False),
        ]
        for key, reader, interval, delay, keep_on_failure in specs:
            thread = threading.Thread(
                target=self._loop,
                args=(key, reader, interval, delay, keep_on_failure),
                daemon=True,
                name="wocli-%s" % key,
            )
            thread.start()
            self._threads.append(thread)

    def _loop(self, key, reader, interval, delay, keep_on_failure):
        if delay and self._stop.wait(delay):
            return
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                value = reader()
            except Exception:
                value = None
            if value is not None or not keep_on_failure:
                self._update(key, value)
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.2, interval - elapsed))

    def _update(self, key: str, value) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot, **{key: value}, captured_at=time.time()
            )

    def snapshot(self) -> StatusSnapshot:
        with self._lock:
            return self._snapshot

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=0.2)
        self._threads = []
