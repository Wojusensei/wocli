"""sys 命令的采集：CPU 采样窗口、macOS 内存口径、取不到数据时的表现."""
import pytest

from helpers import fake_files, shim_run_cmd
from wocli.commands import sys_cmd

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                                    8908.
Pages active:                                170958.
Pages inactive:                              168699.
Pages speculative:                             1820.
Pages wired down:                            181715.
Pages purgeable:                                  4.
Pages occupied by compressor:                459071.
"""


def test_macos_memory_counts_compressed(monkeypatch):
    """已用内存 = active + wired + 压缩页.

    漏掉压缩页会把占用算少好几 G（Apple Silicon 上压缩页能到 7~8G，
    实测把 77% 的占用显示成了 60%）。
    """
    shim_run_cmd(monkeypatch, sys_cmd, [("vm_stat", VM_STAT), ("sysctl", "17179869184\n")])
    used, total = sys_cmd._memory_macos()
    assert total == 17179869184
    assert used == (170958 + 181715 + 459071) * 16384


def test_macos_cpu_uses_last_sample(monkeypatch):
    """必须取最后一份采样.

    top -l 1 只有的第一份采样实测偏高 7~10 个百分点
    （空载 18.9% vs 独立的 iostat 区间值 12.0%），所以要看第二份。
    """
    top = ("CPU usage: 10.12% user, 13.50% sys, 76.36% idle\n"
           "CPU usage: 10.67% user, 7.20% sys, 82.29% idle\n")
    shim_run_cmd(monkeypatch, sys_cmd, [("top", top)])
    assert sys_cmd._cpu_usage_macos() == pytest.approx(17.71, abs=0.01)


def test_macos_cpu_no_output(monkeypatch):
    shim_run_cmd(monkeypatch, sys_cmd, [])
    assert sys_cmd._cpu_usage_macos() is None


STAT_A = "cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 50 0 50 400 0 0 0 0 0 0\n"
STAT_B = "cpu  150 0 150 900 0 0 0 0 0 0\ncpu0 75 0 75 450 0 0 0 0 0 0\n"


def test_cpu_from_proc_stat(monkeypatch):
    """idle 与 iowait 都算"没在干活"."""
    fake_files(monkeypatch, {"/proc/stat": STAT_A})
    assert sys_cmd._cpu_from_proc_stat() == (1000, 800)


def test_cpu_from_proc_stat_incomplete(monkeypatch):
    fake_files(monkeypatch, {"/proc/stat": "cpu  1 2 3\n"})
    assert sys_cmd._cpu_from_proc_stat() is None


def test_linux_cpu_delta(monkeypatch):
    """两次 /proc/stat 的差值才是"当前占用"；没有参照点时返回 None，不编数值."""
    monkeypatch.setattr(sys_cmd, "_CPU_SAMPLE", {"total": None, "idle": None})
    fake_files(monkeypatch, {"/proc/stat": STAT_A})
    assert sys_cmd._cpu_usage_linux() is None    # 两次采样内容相同，差值为 0
    fake_files(monkeypatch, {"/proc/stat": STAT_B})
    assert sys_cmd._cpu_usage_linux() == pytest.approx(50.0)


def test_memory_linux(monkeypatch):
    meminfo = ("MemTotal:       16384000 kB\nMemFree:         1000000 kB\n"
               "MemAvailable:    4096000 kB\nBuffers:          100000 kB\n"
               "Cached:          2000000 kB\n")
    fake_files(monkeypatch, {"/proc/meminfo": meminfo})
    assert sys_cmd._memory_linux() == (12288000 * 1024, 16384000 * 1024)


def test_memory_linux_old_kernel(monkeypatch):
    """3.14 之前的内核没有 MemAvailable，用 free + buffers + cached 近似."""
    meminfo = ("MemTotal:       16384000 kB\nMemFree:         4000000 kB\n"
               "Buffers:          500000 kB\nCached:          3496000 kB\n")
    fake_files(monkeypatch, {"/proc/meminfo": meminfo})
    assert sys_cmd._memory_linux() == (8388000 * 1024, 16384000 * 1024)


def test_memory_linux_no_data(monkeypatch):
    fake_files(monkeypatch, {"/proc/meminfo": ""})
    assert sys_cmd._memory_linux() == (None, None)


def test_draw_missing_data():
    """取不到数据时写"未获取到"，不要留一个看起来正常的 0%."""
    assert sys_cmd.draw_bar("内存", None, None) == "  内存   未获取到"
    assert sys_cmd.draw_cpu(None) == "  CPU    未获取到"


def test_draw_with_data():
    assert "[===============>              ] 50%" in sys_cmd.draw_cpu(50.0)
    assert "11.5GB / 16.0GB" in sys_cmd.draw_bar(
        "磁盘", int(11.5 * 1024 ** 3), 16 * 1024 ** 3)


def test_pad_label_aligns_columns():
    """中文占两列，按显示宽度补齐后 CPU 与 内存 的方括号才对齐."""
    assert len(sys_cmd._pad_label("CPU")) == 6
    assert sys_cmd._pad_label("内存").count(" ") == 2
