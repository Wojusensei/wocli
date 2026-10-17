"""wocli wifi - WiFi 信息与信号强度打分"""

import json
import os
import platform
import re

from wocli.utils import run_cmd

AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
UNKNOWN = "未知"


def _new_info():
    """统一的信息容器：取不到的字段留 None.

    旧实现拿 -100 dBm 当"没取到"的默认值，结果没连 Wi-Fi 也会打出一条
    「D级 · 你这网开了和没开有啥区别」的假评分。
    """
    return {
        "ssid": None,
        "rssi": None,
        "channel": None,
        "bssid": None,
        "security": None,
        "rate": None,
        "note": None,
    }


def _to_int(text):
    try:
        return int(float(str(text).strip()))
    except (TypeError, ValueError):
        return None


def _quality_to_dbm(percent):
    """信号百分比换算 dBm：0% = -100dBm、100% = -50dBm 的经验映射（netsh 也是这套）."""
    return int(percent / 2) - 100


# ---------- macOS ----------

def _macos_security_name(token):
    """把 spairport_security_mode_wpa2_personal 这类机器标识翻成人看的写法."""
    if not token:
        return None
    name = str(token)
    prefix = "spairport_security_mode_"
    if name.startswith(prefix):
        name = name[len(prefix):]
    if name in ("none", "open"):
        return "开放（无加密）"
    words = []
    for word in name.split("_"):
        upper = word.upper()
        if upper in ("WPA", "WPA2", "WPA3", "WEP", "OWE", "EAP"):
            words.append(upper)
        elif upper in ("PERSONAL", "ENTERPRISE"):
            words.append(word.capitalize())
        elif upper == "MIXED":
            words.append("混合")
        elif word:
            words.append(word)
    return " ".join(words) or None


def _fill_from_airport(info, text):
    """macOS 14 之前自带的 airport，字段最全（含 BSSID 和协商速率）."""
    match = re.search(r"^\s*SSID:\s*(.+)$", text, re.M)
    if match:
        info["ssid"] = match.group(1).strip()
    match = re.search(r"agrCtlRSSI:\s*(-?\d+)", text)
    if match:
        info["rssi"] = int(match.group(1))
    match = re.search(r"^\s*channel:\s*(\d+)", text, re.M)
    if match:
        info["channel"] = match.group(1)
    match = re.search(r"^\s*BSSID:\s*([0-9a-fA-F:]{17})", text, re.M)
    if match:
        info["bssid"] = match.group(1)
    match = re.search(r"^\s*link auth:\s*(.+)$", text, re.M)
    if match:
        info["security"] = match.group(1).strip()
    match = re.search(r"lastTxRate:\s*(\d+)", text)
    if match:
        info["rate"] = f"{match.group(1)} Mbps"


def _fill_from_profiler_json(info, text):
    """解析 system_profiler SPAirPortDataType -json，返回 (是否已连接, 是否被打码).

    用 -json 而不是文本：JSON 的键是英文机器名（spairport_*），不随系统语言变；
    文本输出在中文系统上连 "Signal / Noise" 都是本地化的，按标签匹配很脆。
    """
    if not text:
        return False, False
    try:
        data = json.loads(text)
    except ValueError:
        return False, False

    interfaces = []
    for section in data.get("SPAirPortDataType") or []:
        interfaces.extend(section.get("spairport_airport_interfaces") or [])

    for interface in interfaces:
        name = str(interface.get("_name") or "")
        # awdl/llw/nan 是 AirDrop、接力的虚拟接口，不是用户连的那个 Wi-Fi
        if name.startswith(("awdl", "llw", "nan")):
            continue
        status = str(interface.get("spairport_status_information") or "")
        current = interface.get("spairport_current_network_information") or {}
        if "connected" not in status and not current:
            continue

        redacted = False
        ssid = str(current.get("_name") or "").strip()
        if not ssid or ssid.startswith("<redacted"):
            redacted = True
        else:
            info["ssid"] = ssid

        signal_text = str(current.get("spairport_signal_noise") or "")
        match = re.search(r"(-?\d+)\s*dBm", signal_text)
        if match:
            info["rssi"] = int(match.group(1))
        # 保留 "48 (5GHz, 80MHz)" 整串：频段和带宽都在里面
        channel = str(current.get("spairport_network_channel") or "").strip()
        if channel:
            info["channel"] = channel
        security = _macos_security_name(current.get("spairport_security_mode"))
        if security:
            info["security"] = security
        rate = _to_int(current.get("spairport_network_rate"))
        if rate:
            info["rate"] = f"{rate} Mbps"
        return True, redacted

    return False, False


def _macos_wifi():
    info = _new_info()

    if os.path.exists(AIRPORT):
        # macOS Sonoma(14) 起系统移除了 airport，旧系统优先用它
        text = run_cmd([AIRPORT, "-I"], timeout=6)
        if text:
            _fill_from_airport(info, text)
            if info["ssid"] or info["rssi"] is not None:
                return info

    connected, redacted = _fill_from_profiler_json(
        info, run_cmd(["system_profiler", "SPAirPortDataType", "-json"], timeout=30)
    )

    if info["ssid"] is None:
        # networksetup 是另一套查询，没权限时只会回一句
        # "You are not associated with an AirPort network."，认出名字就算赚
        for iface in ("en0", "en1", "en2", "en3"):
            text = run_cmd(["networksetup", "-getairportnetwork", iface], timeout=6)
            match = re.search(r"Current Wi-Fi Network:\s*(.+)", text or "")
            if match and match.group(1).strip():
                info["ssid"] = match.group(1).strip()
                break

    if connected and redacted and info["ssid"] is None:
        info["note"] = ("系统把 Wi-Fi 名称打码了：给终端开定位权限"
                        "（系统设置 → 隐私与安全性 → 定位服务）才能读到名称和 BSSID")
    elif not connected and info["ssid"] is None:
        info["note"] = "当前没有连上 Wi-Fi（可能是在用有线网络，或 Wi-Fi 已关闭）"
    return info


# ---------- Windows ----------

def _windows_wifi():
    info = _new_info()
    text = run_cmd(["netsh", "wlan", "show", "interfaces"], timeout=10) or ""
    if not text.strip():
        info["note"] = "没取到无线网卡信息（可能没有无线网卡，或 WLAN 服务没启动）"
        return info

    lowered = text.lower()
    if "已断开" in text or "disconnected" in lowered:
        info["note"] = "当前没有连上 Wi-Fi（可能是在用有线网络，或 Wi-Fi 已关闭）"

    # (?<!B)SS 排掉 BSSID；中英文系统关键词不同，两组都认
    match = re.search(r"(?<!B)SSID\s*:\s*(.+)", text)
    if match and match.group(1).strip():
        info["ssid"] = match.group(1).strip()

    match = re.search(r"(?:Signal|信号)\s*:\s*(\d+)\s*%", text)
    if match:
        info["rssi"] = _quality_to_dbm(int(match.group(1)))

    match = re.search(r"(?:Channel|信道)\s*:\s*(\d+)", text)
    if match:
        info["channel"] = match.group(1)

    match = re.search(r"BSSID\s*:\s*([0-9A-Fa-f:]{17})", text)
    if match:
        info["bssid"] = match.group(1)

    match = re.search(r"(?:Authentication|身份验证)\s*:\s*(.+)", text)
    if match and match.group(1).strip():
        info["security"] = match.group(1).strip()

    match = re.search(r"(?:Receive rate|接收速率)\s*\(Mbps\)\s*:\s*([\d.]+)", text)
    if match:
        info["rate"] = f"{match.group(1)} Mbps"

    if "没有运行" in text or "is not running" in lowered:
        info["note"] = "WLAN 自动配置服务可能没启动，netsh 取不到无线状态"
    return info


# ---------- Linux ----------

def _split_escaped(text, sep=":"):
    """nmcli -t 用 ':' 分隔字段，字段内部的 ':' 会转义成 '\\:'，不能直接 split."""
    fields = []
    current = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == sep:
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def _freq_to_channel(freq):
    """iw 只给中心频率，按频段换算成信道号."""
    if 2412 <= freq <= 2484:
        return 14 if freq == 2484 else (freq - 2407) // 5
    if 5000 <= freq < 5900:
        return (freq - 5000) // 5
    if 5955 <= freq <= 7115:
        return (freq - 5950) // 5
    return None


def _fill_from_nmcli(info):
    """NetworkManager 一条命令就能给全 SSID/信号/信道/加密，现代发行版基本都有."""
    text = run_cmd([
        "nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,CHAN,SECURITY",
        "dev", "wifi", "list", "--rescan", "no",
    ], timeout=10)
    if not text:
        return False
    for line in text.splitlines():
        fields = _split_escaped(line)
        if len(fields) < 5 or fields[0].strip() != "*":
            continue
        if fields[1] and fields[1] != "--":
            info["ssid"] = fields[1]
        signal = _to_int(fields[2])
        if signal:
            # nmcli 只给百分比，换算成 dBm 才能和评分表对齐
            info["rssi"] = _quality_to_dbm(signal)
            info["note"] = "信号强度由 NetworkManager 的百分比换算成 dBm"
        if fields[3] and fields[3] != "--":
            info["channel"] = fields[3]
        if fields[4] and fields[4] != "--":
            info["security"] = fields[4]
        return True
    return False


def _linux_wireless_iface():
    """找无线网卡名：wlan0 只是常见命名，也有 wlp3s0、wlx... 等."""
    text = run_cmd(["iw", "dev"], timeout=6)
    match = re.search(r"Interface\s+(\S+)", text or "")
    if match:
        return match.group(1)
    try:
        with open("/proc/net/wireless", "r") as handle:
            rows = handle.read().splitlines()[2:]
    except OSError:
        return None
    for row in rows:
        if ":" in row:
            return row.split(":", 1)[0].strip()
    return None


def _fill_from_iw(info, iface):
    if not iface:
        return False
    text = run_cmd(["iw", "dev", iface, "link"], timeout=6)
    if not text or "Not connected" in text:
        return False

    match = re.search(r"SSID:\s*(.+)", text)
    if match and match.group(1).strip():
        info["ssid"] = match.group(1).strip()
    match = re.search(r"signal:\s*(-?\d+)\s*dBm", text)
    if match:
        info["rssi"] = int(match.group(1))
    match = re.search(r"freq:\s*(\d+)", text)
    if match:
        channel = _freq_to_channel(int(match.group(1)))
        if channel:
            info["channel"] = str(channel)
    match = re.search(r"tx bitrate:\s*([\d.]+)", text)
    if match:
        info["rate"] = f"{match.group(1)} Mbps"
    match = re.search(r"Connected to\s+([0-9A-Fa-f:]{17})", text)
    if match:
        info["bssid"] = match.group(1)
    return bool(info["ssid"] or info["rssi"] is not None)


def _fill_from_proc_wireless(info):
    """没有 nmcli/iw 时的兜底：/proc/net/wireless 给 level(dBm)，但给不出 SSID."""
    try:
        with open("/proc/net/wireless", "r") as handle:
            rows = handle.read().splitlines()[2:]
    except OSError:
        return False
    for row in rows:
        if ":" not in row:
            continue
        fields = row.split(":", 1)[1].split()
        if len(fields) < 3:
            continue
        level = _to_int(fields[2].rstrip("."))
        if level is None:
            continue
        # 现代驱动这里就是 dBm；少数老驱动给的是质量百分比
        if level < 0:
            info["rssi"] = level
        else:
            info["rssi"] = _quality_to_dbm(level)
            info["note"] = "信号强度由驱动给的质量值换算"
        if info["ssid"] is None:
            ssid = (run_cmd(["iwgetid", "-r"], timeout=5) or "").strip()
            if ssid:
                info["ssid"] = ssid
        return True
    return False


def _fill_from_iwconfig(info):
    text = run_cmd(["iwconfig"], timeout=6)
    if not text or "ESSID" not in text:
        return False

    match = re.search(r'ESSID:"([^"]+)"', text)
    essid = match.group(1).strip() if match else ""
    if essid and essid.lower() not in ("off/any", "off", "any"):
        info["ssid"] = essid

    # Signal level 有两种写法：dBm（"-60 dBm"）和质量（"60/100"）。
    # 旧实现直接取整，会把质量 60 当成 +60 dBm，等于把差信号判成满格
    match = re.search(r"Signal level[=:]\s*(-?\d+)\s*dBm", text)
    if match:
        info["rssi"] = int(match.group(1))
    else:
        match = re.search(r"Signal level[=:]\s*(\d+)\s*/\s*(\d+)", text)
        if match:
            total = _to_int(match.group(2)) or 100
            info["rssi"] = _quality_to_dbm(int(match.group(1)) * 100.0 / total)
            info["note"] = "信号强度由驱动给的质量值换算"
        else:
            match = re.search(r"Signal level[=:]\s*(-?\d+)", text)
            if match:
                value = int(match.group(1))
                if value < 0:
                    info["rssi"] = value
                else:
                    info["rssi"] = _quality_to_dbm(value)
                    info["note"] = "信号强度由驱动给的质量值换算"

    match = re.search(r"Access Point:\s*([0-9A-Fa-f:]{17})", text)
    if match:
        info["bssid"] = match.group(1)
    match = re.search(r"Bit Rate[=:]\s*([\d.]+)", text)
    if match:
        info["rate"] = f"{match.group(1)} Mb/s"

    return bool(info["ssid"] or info["rssi"] is not None)


def _linux_wifi():
    info = _new_info()
    if _fill_from_nmcli(info):
        return info
    iface = _linux_wireless_iface()
    if _fill_from_iw(info, iface):
        return info
    if _fill_from_proc_wireless(info):
        return info
    if _fill_from_iwconfig(info):
        return info
    info["note"] = "没取到无线信息（可能没有无线网卡；装 NetworkManager 或 wireless-tools 后更全）"
    return info


# ---------- 打分与输出 ----------

def score_signal(rssi):
    """按 dBm 打分；拿不到信号值时返回 (None, None)，不要编一个 -100 出来."""
    if rssi is None:
        return None, None
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
        info = _macos_wifi()
    elif system == "Windows":
        info = _windows_wifi()
    else:
        info = _linux_wifi()

    signal_pct, grade = score_signal(info["rssi"])
    bar_len = 20

    print()
    print(f"  网络名称：{info['ssid'] or UNKNOWN}")
    if signal_pct is None:
        print(f"  信号强度：{UNKNOWN}")
    else:
        filled = int(bar_len * signal_pct / 100)
        bar = "=" * filled + "-" * (bar_len - filled)
        print(f"  信号强度：[{bar}] {signal_pct:.2f}%")
        print(f"  RSSI：{info['rssi']} dBm")
        print(f"  评级：{grade}")
    print(f"  信道：{info['channel'] or UNKNOWN}")
    print(f"  加密：{info['security'] or UNKNOWN}")
    if info["rate"]:
        print(f"  速率：{info['rate']}")
    print(f"  BSSID：{info['bssid'] or UNKNOWN}")
    if info["note"]:
        print(f"  提示：{info['note']}")
    print()
