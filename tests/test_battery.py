"""battery 命令的跨平台解析：充电状态、健康度数据、缺数据不许凑分."""
import pytest

from helpers import fake_files, set_platform, shim_run_cmd
from wocli.commands import battery

PMSET_CASES = [
    # 限充状态：这里含 "not charging"，旧实现按 "charging" 匹配会误报成"充电中"
    (" -InternalBattery-0 (id=1)\t80%; AC attached; not charging present: true",
     80, "已接电源（未充电）"),
    (" -InternalBattery-0 (id=1)\t98%; charging; 0:12 remaining present: true",
     98, "充电中"),
    # 放电状态里也有 "charging" 子串，必须先判 discharging
    (" -InternalBattery-0 (id=1)\t75%; discharging; 3:20 remaining present: true",
     75, "使用中"),
    (" -InternalBattery-0 (id=1)\t100%; charged; 0:00 remaining present: true",
     100, "已充满"),
    (" -InternalBattery-0 (id=1)\t97%; finishing charge; AC attached present: true",
     97, "充电中（即将充满）"),
    # 台式机/没电池：只有这一行
    ("Now drawing from 'AC Power'\n", None, "未知"),
]


@pytest.mark.parametrize("text,expect_percent,expect_status", PMSET_CASES)
def test_pmset_status(text, expect_percent, expect_status):
    assert battery._parse_pmset_batt(text) == (expect_percent, expect_status)


IOREG = ('|"CycleCount"=9|"MaxCapacity"=100|"BatteryData"={"FullChargeCapacity"=4712,'
         '"DesignCapacity"=4629,"CurrentCapacity"=80}')


def test_ioreg_health():
    """ioreg 的键带引号（"CycleCount" = 9），解析要认引号和等号两侧的空白."""
    assert battery._macos_health_from_ioreg(IOREG) == (9, 100)


def test_ioreg_health_computes_capacity():
    """没有 MaxCapacity 百分比时，用 满充容量 / 设计容量 反算."""
    text = '|"CycleCount"=412|"BatteryData"={"FullChargeCapacity"=47320,"DesignCapacity"=52000}'
    assert battery._macos_health_from_ioreg(text) == (412, 91)


def test_int_after_ignores_suffix_keys():
    """ioreg 里同时存在 FedDesignCapacity 和 DesignCapacity，不能匹配到前者."""
    text = '"FedDesignCapacity"=0 "DesignCapacity"=4629 "FullChargeCapacity"=4712'
    assert battery._int_after(text, "DesignCapacity") == 4629
    assert battery._int_after(text, "FullChargeCapacity") == 4712


def test_system_profiler_fallback():
    text = ("          Cycle Count: 33\n"
            "          Condition: Normal\n"
            "          Maximum Capacity: 89%\n")
    assert battery._macos_health_from_profiler(text) == (33, 89)


@pytest.mark.parametrize("raw,expect", [
    ("85|2", (85, "已接电源（未充电）")),
    # Win32_Battery 的状态 6~9 才是"充电中"，旧实现只映射了 1/2/3
    ("60|6", (60, "充电中")),
    ("60|7", (60, "充电中（高电量）")),
    ("40|1", (40, "使用中")),
    ("100|3", (100, "已充满")),
    ("77|11", (77, "已接电源（半充）")),
])
def test_windows_battery_status(monkeypatch, raw, expect):
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, battery, [("Win32_Battery", raw), ("powercfg", None)])
    result = battery.get_battery_windows()
    assert (result[0], result[1]) == expect


def test_windows_no_battery(monkeypatch):
    """Win32_Battery 查不到（台式机）时返回空数据，不猜."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, battery, [("Win32_Battery", ""), ("powercfg", None)])
    assert battery.get_battery_windows() == (None, "未知", None, None, None)


POWERCFG_XML = """<?xml version="1.0" encoding="utf-8"?>
<BatteryReport xmlns="http://schemas.microsoft.com/powershell/2004/04">
  <Batteries>
    <Battery>
      <Id>0</Id>
      <DesignCapacity>52000</DesignCapacity>
      <FullChargeCapacity>47320</FullChargeCapacity>
      <CycleCount>412</CycleCount>
    </Battery>
  </Batteries>
</BatteryReport>
"""


def test_windows_health_from_powercfg(monkeypatch):
    """powercfg 的 XML 带命名空间，解析要按标签名尾部匹配，容量算成百分比."""
    def fake(cmd, timeout=6):
        if "powercfg" in cmd:
            with open(cmd[cmd.index("/output") + 1], "w") as handle:
                handle.write(POWERCFG_XML)
            return ""
        return None
    monkeypatch.setattr(battery, "run_cmd", fake)
    assert battery._windows_health_from_powercfg() == (412, 91)


def test_windows_health_unavailable(monkeypatch):
    """powercfg 用不了（或没生成报告）时返回空，不能编一个容量出来."""
    shim_run_cmd(monkeypatch, battery, [])
    assert battery._windows_health_from_powercfg() == (None, None)


def _write_supply(root, name, **fields):
    """按 sysfs 的样子造一棵假的 /sys/class/power_supply 树."""
    directory = root / name
    directory.mkdir()
    for key, value in fields.items():
        (directory / key).write_text(str(value))


def test_linux_single_battery(monkeypatch, tmp_path):
    """电池目录名不一定是 BAT0，要按 type=Battery 认；健康度从内核数据算出来."""
    _write_supply(tmp_path, "AC", type="Mains")
    _write_supply(tmp_path, "BAT0", type="Battery", capacity=64, status="Not charging",
                  cycle_count=228, energy_full=41000000, energy_full_design=57000000,
                  temp=305)
    monkeypatch.setattr(battery, "POWER_SUPPLY_DIR", str(tmp_path))
    assert battery.get_battery_linux() == (64, "已接电源（未充电）", 228, 72, 30.5)


def test_linux_two_batteries(monkeypatch, tmp_path):
    """两块电池按容量加权算总电量，否则会出现"60% 和 80% 平均成 70%"的错值."""
    _write_supply(tmp_path, "BAT0", type="Battery", capacity=80, status="Discharging",
                  cycle_count=412, energy_full=47320000, energy_full_design=52000000)
    _write_supply(tmp_path, "BAT1", type="Battery", capacity=60, status="Discharging",
                  cycle_count=100, energy_full=20000000, energy_full_design=21000000)
    monkeypatch.setattr(battery, "POWER_SUPPLY_DIR", str(tmp_path))
    percent, status, cycles, max_cap, _temp = battery.get_battery_linux()
    assert percent == 74          # (80*47.32 + 60*20) / 67.32
    assert status == "使用中"
    assert cycles == 412
    assert max_cap == 92          # 67.32 / 73.0


def test_linux_android_style(monkeypatch, tmp_path):
    """安卓/Termux 的电池节点只有 charge_full 系列，没有 energy_* 和循环次数."""
    _write_supply(tmp_path, "battery", type="Battery", capacity=77, status="Charging",
                  charge_full=3000000, charge_full_design=4000000)
    monkeypatch.setattr(battery, "POWER_SUPPLY_DIR", str(tmp_path))
    percent, status, cycles, max_cap, _temp = battery.get_battery_linux()
    assert (percent, status, cycles, max_cap) == (77, "充电中", None, 75)


def test_linux_no_battery(monkeypatch, tmp_path):
    """台式机/虚拟机没有电池目录时返回空数据."""
    monkeypatch.setattr(battery, "POWER_SUPPLY_DIR", str(tmp_path))
    assert battery.get_battery_linux() == (None, "未知", None, None, None)


def test_score_without_health_data():
    """只有电量能读时，评分就等于电量本身，不能靠缺项按满分补出个虚高分."""
    assert battery.score_battery(80, None, None)[0] == 80
    assert battery.score_battery(None, None, None) == (None, "无数据")


def test_score_with_all_data():
    """三项齐全时按 0.3 / 0.3 / 0.4 加权."""
    assert battery.score_battery(80, 412, 91)[0] == 78.04
