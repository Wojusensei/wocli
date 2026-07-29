"""wocli wifi - WiFi 信息与信号强度打分"""
import subprocess
import platform
import re


def get_wifi_macos():
    try:
        # 获取当前 WiFi 名称
        info = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
            capture_output=True, text=True
        )
        ssid = re.search(r"\s*SSID:\s*(.+)", info.stdout)
        ssid = ssid.group(1).strip() if ssid else "未知"

        rssi = re.search(r"\s*agrCtlRSSI:\s*(-?\d+)", info.stdout)
        rssi = int(rssi.group(1)) if rssi else -100

        channel = re.search(r"\s*channel:\s*(\d+)", info.stdout)
        channel = channel.group(1) if channel else "未知"

        # 获取加密方式和 MAC
        bssid = re.search(r"\s*BSSID:\s*([0-9a-f:]+)", info.stdout)
        bssid = bssid.group(1).strip() if bssid else "未知"

        security = re.search(r"\s*link auth:\s*(.+)", info.stdout)
        security = security.group(1).strip() if security else "未知"

        return ssid, rssi, channel, bssid, security
    except:
        return "未知", -100, "未知", "未知", "未知"


def get_wifi_windows():
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True
        )
        ssid = re.search(r"SSID\s*:\s*(.+)", result.stdout)
        ssid = ssid.group(1).strip() if ssid else "未知"

        rssi = re.search(r"Signal\s*:\s*(\d+)%", result.stdout)
        signal_pct = int(rssi.group(1)) if rssi else 0
        rssi = int((signal_pct / 2) - 100) if signal_pct > 0 else -100

        channel = re.search(r"Channel\s*:\s*(\d+)", result.stdout)
        channel = channel.group(1) if channel else "未知"

        bssid = re.search(r"BSSID\s*:\s*([0-9A-Fa-f:]+)", result.stdout)
        bssid = bssid.group(1).strip() if bssid else "未知"

        security = "WPA2" 
        return ssid, rssi, channel, bssid, security
    except:
        return "未知", -100, "未知", "未知", "未知"


def get_wifi_linux():
    try:
        result = subprocess.run(["iwconfig"], capture_output=True, text=True, stderr=subprocess.DEVNULL)
        ssid = re.search(r'ESSID:"(.+)"', result.stdout)
        ssid = ssid.group(1) if ssid else "未知"

        rssi = re.search(r"Signal level=(-?\d+)", result.stdout)
        rssi = int(rssi.group(1)) if rssi else -100

        return ssid, rssi, "未知", "未知", "未知"
    except:
        return "未知", -100, "未知", "未知", "未知"


def score_signal(rssi):
    if rssi > -50:
        pct = 100.0
        grade = "S级 · 你这网络真的可以做任何事情。"
    elif rssi > -60:
        pct = 85 + (rssi + 60) * 1.5
        grade = "A级 · 看4K无压力。"
    elif rssi > -70:
        pct = 60 + (rssi + 70) * 2.5
        grade = "B级 · 刷刷视频应该是没有问题的。"
    elif rssi > -80:
        pct = 25 + (rssi + 80) * 3.5
        grade = "C级 · 聊天不满意发表情包。"
    else:
        pct = max(0, 5 + (rssi + 90) * 0.5)
        grade = "D级 · 你这网开了和没开有啥区别。"

    pct = min(100, max(0, pct))
    return round(pct, 2), grade


def run():
    system = platform.system()
    if system == "Darwin":
        ssid, rssi, channel, bssid, security = get_wifi_macos()
    elif system == "Windows":
        ssid, rssi, channel, bssid, security = get_wifi_windows()
    else:
        ssid, rssi, channel, bssid, security = get_wifi_linux()

    signal_pct, grade = score_signal(rssi)
    bar_len = 20
    filled = int(bar_len * signal_pct / 100)
    bar = "=" * filled + "-" * (bar_len - filled)

    print()
    print(f"  网络名称：{ssid}")
    print(f"  信号强度：[{bar}] {signal_pct:.2f}%")
    print(f"  RSSI：{rssi} dBm")
    print(f"  评级：{grade}")
    print(f"  信道：{channel}")
    print(f"  加密：{security}")
    print(f"  BSSID：{bssid}")
    print()