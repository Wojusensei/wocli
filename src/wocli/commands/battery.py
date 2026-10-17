"""wocli battery - 电池信息与健康度打分"""

import os
import platform
import re
import tempfile
import xml.etree.ElementTree as ET

from wocli.utils import run_cmd

UNKNOWN = "未知"
# Linux 的电池目录名不固定（BAT0/BAT1/CMB0/macsmc-battery...），只能遍历后按 type 认
POWER_SUPPLY_DIR = "/sys/class/power_supply"


def _to_int(text):
    try:
        return int(float(str(text).strip()))
    except (TypeError, ValueError):
        return None


def _int_after(text, key):
    """取 "Cycle Count: 9" / '"CycleCount" = 9' 这类键值里的整数.

    ioreg 的键带双引号、等号两边还有空格，所以引号和空白都要容忍；
    键名前面加 (?<![A-Za-z0-9]) 是为了不误匹配 "FedDesignCapacity" 里的 "DesignCapacity"。
    """
    if not text:
        return None
    pattern = r'(?<![A-Za-z0-9])"?%s"?\s*[:=]\s*(-?\d+)' % re.escape(key)
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _read_text(path):
    try:
        with open(path, "r") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _read_int(path):
    return _to_int(_read_text(path))


# ---------- macOS ----------

def _pmset_status(text):
    """把 pmset 的状态文本翻成中文.

    pmset 的状态是分号分隔的自由文本："80%; AC attached; not charging present: true"。
    这里必须先判 "discharging" 和 "not charging"：它俩都含有 "charging"，
    顺序反了就会把没在充电的电池报成「充电中」。
    """
    lowered = text.lower()
    if "discharging" in lowered:
        return "使用中"
    if "not charging" in lowered:
        return "已接电源（未充电）"
    if "finishing charge" in lowered:
        return "充电中（即将充满）"
    if "charging" in lowered:
        return "充电中"
    if "charged" in lowered:
        return "已充满"
    if "ac attached" in lowered:
        return "已接电源（未充电）"
    return UNKNOWN


def _parse_pmset_batt(text):
    """从 pmset -g batt 取 (电量, 充电状态)，取不到给 (None, 未知)."""
    for line in (text or "").splitlines():
        match = re.search(r"(\d{1,3})%", line)
        if not match:
            continue
        percent = int(match.group(1))
        if not 0 <= percent <= 100:
            continue
        state_text = line.split(";", 1)[1] if ";" in line else ""
        return percent, _pmset_status(state_text)
    return None, UNKNOWN


def _macos_health_from_ioreg(text):
    """ioreg 直接给出循环次数和最大容量，比 system_profiler 快一个数量级（后者要好几秒）."""
    cycles = _int_after(text, "CycleCount")
    max_cap = _int_after(text, "MaxCapacity")
    design = _int_after(text, "DesignCapacity")
    full = _int_after(text, "FullChargeCapacity")
    if design and full and design > 0:
        max_cap = max_cap if max_cap else round(full * 100 / design)
    return cycles, max_cap


def _macos_health_from_profiler(text):
    return _int_after(text, "Cycle Count"), _int_after(text, "Maximum Capacity")


def get_battery_macos():
    percent, status = _parse_pmset_batt(run_cmd(["pmset", "-g", "batt"], timeout=6))
    if percent is None:
        return None, status, None, None, None

    ioreg = run_cmd(["ioreg", "-rn", "AppleSmartBattery"], timeout=8)
    cycles, max_cap = _macos_health_from_ioreg(ioreg)
    if cycles is None and max_cap is None:
        cycles, max_cap = _macos_health_from_profiler(
            run_cmd(["system_profiler", "SPPowerDataType"], timeout=30)
        )
    if max_cap is not None and not 1 <= max_cap <= 150:
        max_cap = None
    return percent, status, cycles, max_cap, None


# ---------- Windows ----------

# Win32_Battery.BatteryStatus 的完整取值：旧实现只映射了 1/2/3，
# 真正在充电（6~9）反而会显示成「未知」
WIN_BATTERY_STATUS = {
    "1": "使用中",                 # Other：文档语义就是放电中
    "2": "已接电源（未充电）",       # 接了 AC，但不一定在充电
    "3": "已充满",
    "4": "使用中（电量低）",
    "5": "使用中（电量危急）",
    "6": "充电中",
    "7": "充电中（高电量）",
    "8": "充电中（低电量）",
    "9": "充电中（电量危急）",
    "11": "已接电源（半充）",
}


def _windows_health_from_powercfg():
    """powercfg 的 XML 报告里有设计容量/满充容量/循环次数——Win32_Battery 不提供这些.

    报告只能落到文件再解析；拿不到就当健康数据缺失，不猜数值。
    """
    try:
        with tempfile.TemporaryDirectory(prefix="wocli-batt-") as tmp:
            path = os.path.join(tmp, "battery.xml")
            run_cmd(["powercfg", "/batteryreport", "/xml", "/output", path], timeout=30)
            if not os.path.exists(path):
                return None, None
            tree = ET.parse(path)
    except Exception:
        return None, None

    design = full = cycles = None
    for node in tree.iter():
        # 命名空间在不同 Windows 版本上不一样，按标签名尾部匹配
        name = node.tag.rsplit("}", 1)[-1].lower()
        value = _to_int(node.text)
        if value is None:
            continue
        if name == "designcapacity":
            design = (design or 0) + value
        elif name == "fullchargecapacity":
            full = (full or 0) + value
        elif name == "cyclecount" and cycles is None:
            cycles = value

    max_cap = None
    if design and full:
        ratio = round(full * 100 / design)
        if 5 <= ratio <= 150:
            max_cap = ratio
    return cycles, max_cap


def get_battery_windows():
    out = run_cmd([
        "powershell", "-NoProfile", "-Command",
        "$b = Get-CimInstance Win32_Battery | Select-Object -First 1; "
        "if ($b) { '{0}|{1}' -f $b.EstimatedChargeRemaining, $b.BatteryStatus }",
    ], timeout=15)
    text = (out or "").strip()
    if "|" not in text:
        return None, UNKNOWN, None, None, None

    raw_percent, _, raw_status = text.partition("|")
    percent = _to_int(raw_percent)
    if percent is None or not 0 <= percent <= 100:
        return None, UNKNOWN, None, None, None
    status = WIN_BATTERY_STATUS.get(raw_status.strip(), UNKNOWN)

    # 只在确实检测到电池时才去生成报告：powercfg 要一两秒，台式机上白等
    cycles, max_cap = _windows_health_from_powercfg()
    return percent, status, cycles, max_cap, None


# ---------- Linux ----------

LINUX_BATTERY_STATUS = {
    "charging": "充电中",
    "discharging": "使用中",
    "full": "已充满",
    "not charging": "已接电源（未充电）",
    "unknown": UNKNOWN,
}


def get_battery_linux():
    """遍历 /sys/class/power_supply：目录名不必是 BAT0，有的机器还有两块电池.

    顺带把内核给的循环次数、满充/设计容量读出来，健康度就有真数据可算了
    （旧实现在 Linux 上把最大容量写死 100，等于永远满分）。
    """
    if not os.path.isdir(POWER_SUPPLY_DIR):
        return None, UNKNOWN, None, None, None

    percents = []
    full_sum = 0.0
    design_sum = 0.0
    status = UNKNOWN
    cycles = None
    temp = None
    detected = False

    for name in sorted(os.listdir(POWER_SUPPLY_DIR)):
        base = os.path.join(POWER_SUPPLY_DIR, name)
        if _read_text(os.path.join(base, "type")).lower() != "battery":
            continue
        detected = True

        energy_full = _read_int(os.path.join(base, "energy_full"))
        energy_now = _read_int(os.path.join(base, "energy_now"))
        charge_full = _read_int(os.path.join(base, "charge_full"))
        charge_now = _read_int(os.path.join(base, "charge_now"))
        full = energy_full if energy_full is not None else charge_full
        now = energy_now if energy_now is not None else charge_now
        design = _read_int(os.path.join(base, "energy_full_design"))
        if design is None:
            design = _read_int(os.path.join(base, "charge_full_design"))

        capacity = _read_int(os.path.join(base, "capacity"))
        if capacity is not None and 0 <= capacity <= 100:
            percents.append((capacity, full or 0))
        elif full and now is not None:
            percents.append((now * 100.0 / full, full))

        if full and design:
            full_sum += full
            design_sum += design

        if status == UNKNOWN:
            raw = _read_text(os.path.join(base, "status")).lower()
            status = LINUX_BATTERY_STATUS.get(raw, raw or UNKNOWN)
        if cycles is None:
            cycles = _read_int(os.path.join(base, "cycle_count"))
        if temp is None:
            raw_temp = _read_int(os.path.join(base, "temp"))
            # sysfs 的 temp 单位是 0.1℃，安卓的 battery 节点同单位
            if raw_temp is not None and 0 < raw_temp < 1200:
                temp = round(raw_temp / 10.0, 1)

    if not detected or not percents:
        return None, UNKNOWN, None, None, None

    weight_sum = sum(weight for _, weight in percents)
    if weight_sum > 0:
        percent = round(sum(value * weight for value, weight in percents) / weight_sum)
    else:
        percent = round(sum(value for value, _ in percents) / len(percents))

    max_cap = round(full_sum * 100 / design_sum) if design_sum else None
    if max_cap is not None and not 5 <= max_cap <= 150:
        max_cap = None
    return percent, status, cycles, max_cap, temp


# ---------- 打分 ----------

def score_battery(percent, cycles, max_cap):
    """按可用数据加权，缺项按比例归一，不拿满分去补.

    旧实现里循环次数缺失按 100 分、最大容量缺失也按 100 分，
    于是只有电量可读的机器永远「S 级」，看着像健康度其实只是电量分。
    """
    parts = []
    if percent is not None:
        parts.append((0.3, percent))
    if cycles is not None:
        parts.append((0.3, max(0.0, 100 - cycles * 0.1)))
    if max_cap is not None:
        parts.append((0.4, max_cap))
    if not parts:
        return None, "无数据"

    weight_sum = sum(weight for weight, _ in parts)
    total = sum(weight * value for weight, value in parts) / weight_sum
    total = min(100.0, total)

    if total >= 95:
        grade = "S级 · 古希腊掌管电池的神"
    elif total >= 85:
        grade = "A级 · 还能战三年"
    elif total >= 70:
        grade = "B级 · 电池有点虚了"
    elif total >= 50:
        grade = "C级 · 已经离不开充电器"
    else:
        grade = "D级 · 电池这么老，零百加速只要三十分钟吧"

    return round(total, 2), grade


def run():
    system = platform.system()
    if system == "Darwin":
        percent, status, cycles, max_cap, temp = get_battery_macos()
    elif system == "Windows":
        percent, status, cycles, max_cap, temp = get_battery_windows()
    else:
        percent, status, cycles, max_cap, temp = get_battery_linux()

    if percent is None:
        print("\n  未获取到电池信息（台式机、虚拟机通常没有电池）。\n")
        return

    score_val, grade = score_battery(percent, cycles, max_cap)
    bar_len = 20
    filled = int(bar_len * percent / 100)
    bar = "=" * filled + "-" * (bar_len - filled)

    print()
    print(f"  当前电量：[{bar}] {percent}%")
    print(f"  充电状态：{status}")
    if cycles is not None:
        print(f"  循环次数：{cycles} 次")
    if max_cap is not None:
        print(f"  最大容量：{max_cap}%")
    if temp is not None:
        print(f"  电池温度：{temp} °C")
    print(f"  健康评分：{score_val:.2f} / 100.00")
    print(f"  评级：{grade}")
    if cycles is None and max_cap is None:
        print("  （拿不到循环次数/最大容量，评分主要由当前电量决定）")
    print()
