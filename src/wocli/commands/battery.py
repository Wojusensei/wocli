"""wocli battery - 电池信息与健康度打分"""
import subprocess
import platform
import re


def get_battery_macos():
    try:
        result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True)
        output = result.stdout
        # 电量
        pct_match = re.search(r"(\d{1,3})%", output)
        percent = int(pct_match.group(1)) if pct_match else -1
        # 充电状态
        status = "未知"
        if "charging" in output:
            status = "充电中"
        elif "discharging" in output:
            status = "使用中"
        elif "charged" in output:
            status = "已充满"
        # 健康度和循环次数
        try:
            health = subprocess.run(
                ["system_profiler", "SPPowerDataType"],
                capture_output=True, text=True
            )
            cycles_match = re.search(r"Cycle Count:\s*(\d+)", health.stdout)
            cycles = int(cycles_match.group(1)) if cycles_match else -1
            max_match = re.search(r"Maximum Capacity:\s*(\d+)%", health.stdout)
            max_cap = int(max_match.group(1)) if max_match else 100
        except Exception:
            cycles = -1
            max_cap = 100
        return percent, status, cycles, max_cap
    except Exception:
        return -1, "未知", -1, 100


def get_battery_windows():
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_Battery", "get", "EstimatedChargeRemaining,EstimatedRunTime,BatteryStatus"],
            capture_output=True, text=True
        )
        lines = [l.strip() for l in result.stdout.split("\n") if l.strip()]
        if len(lines) < 2:
            return -1, "未知", -1, 100
        # wmic 输出的列按字母序排列，与请求顺序无关，必须按表头名取值
        info = dict(zip(lines[0].split(), lines[1].split()))
        try:
            percent = int(info.get("EstimatedChargeRemaining", -1))
        except ValueError:
            percent = -1
        status_map = {"1": "使用中", "2": "充电中", "3": "已充满"}
        status = status_map.get(info.get("BatteryStatus", ""), "未知")
        return percent, status, -1, 100
    except Exception:
        return -1, "未知", -1, 100


def get_battery_linux():
    try:
        with open("/sys/class/power_supply/BAT0/capacity", "r") as f:
            percent = int(f.read().strip())
        with open("/sys/class/power_supply/BAT0/status", "r") as f:
            raw = f.read().strip()
            status_map = {"Discharging": "使用中", "Charging": "充电中", "Full": "已充满"}
            status = status_map.get(raw, raw)
        return percent, status, -1, 100
    except Exception:
        return -1, "未知", -1, 100


def score_battery(percent, cycles, max_cap):
    if percent < 0:
        return 0, "无数据"
    charge_score = percent
    if cycles > 0:
        cycle_score = max(0, 100 - cycles * 0.1)
    else:
        cycle_score = 100
    health_score = max_cap
    total = charge_score * 0.3 + cycle_score * 0.3 + health_score * 0.4
    total = min(100, total)

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
        percent, status, cycles, max_cap = get_battery_macos()
    elif system == "Windows":
        percent, status, cycles, max_cap = get_battery_windows()
    else:
        percent, status, cycles, max_cap = get_battery_linux()

    if percent < 0:
        print("\n  无法获取电池信息。\n")
        return

    score_val, grade = score_battery(percent, cycles, max_cap)
    bar_len = 20
    filled = int(bar_len * percent / 100)
    bar = "=" * filled + "-" * (bar_len - filled)

    print()
    print(f"  当前电量：[{bar}] {percent}%")
    print(f"  充电状态：{status}")
    if cycles >= 0:
        print(f"  循环次数：{cycles} 次")
    if max_cap < 100:
        print(f"  最大容量：{max_cap}%")
    print(f"  健康评分：{score_val:.2f} / 100.00")
    print(f"  评级：{grade}")
    print()