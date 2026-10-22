"""wifi 命令的跨平台解析：信号值来源、未连接/打码状态、不能编造信号."""
import json

import pytest

from helpers import fake_files, set_platform, shim_run_cmd
from wocli.commands import wifi_cmd

AIRPORT = """     agrCtlRSSI: -58
    agrCtlNoise: -92
          state: running
       lastTxRate: 866
          channel: 149
       link auth: wpa2-psk
           SSID: HomeWiFi
          BSSID: 3c:37:86:12:34:56
"""


def _profiler_json(ssid="MyWiFi5G\n", status="spairport_status_connected", neighbor=None):
    """构造 system_profiler SPAirPortDataType -json 的结构（键名是英文机器名）."""
    current = {
        "spairport_network_channel": "48 (5GHz, 80MHz)",
        "spairport_network_rate": 292,
        "spairport_security_mode": "spairport_security_mode_wpa2_personal",
        "spairport_signal_noise": "-63 dBm / -96 dBm",
    }
    if ssid is not None:
        current["_name"] = ssid
    interface = {"_name": "en0", "spairport_status_information": status,
                 "spairport_current_network_information": current}
    if neighbor is not None:
        interface["spairport_airport_other_local_wireless_networks"] = [neighbor]
    return json.dumps({"SPAirPortDataType": [{"spairport_airport_interfaces": [
        {"_name": "awdl0", "spairport_supported_channels": []},
        interface,
    ]}]}, ensure_ascii=False)


def test_macos_airport_parse():
    """macOS 14 以前自带的 airport，字段最全（含 BSSID 与协商速率）."""
    info = wifi_cmd._new_info()
    wifi_cmd._fill_from_airport(info, AIRPORT)
    assert (info["ssid"], info["rssi"], info["channel"], info["bssid"],
            info["security"], info["rate"]) == (
        "HomeWiFi", -58, "149", "3c:37:86:12:34:56", "wpa2-psk", "866 Mbps")


def test_macos_json_parse():
    """JSON 模式：名字要 strip，信道保留频段信息，加密方式翻译成人话."""
    info = wifi_cmd._new_info()
    connected, redacted = wifi_cmd._fill_from_profiler_json(info, _profiler_json())
    assert (connected, redacted) == (True, False)
    assert (info["ssid"], info["rssi"], info["channel"], info["security"], info["rate"]) == (
        "MyWiFi5G", -63, "48 (5GHz, 80MHz)", "WPA2 Personal", "292 Mbps")


def test_macos_json_ignores_neighbor_signal():
    """附近网络比当前网络信号强时，不能取到邻居的值."""
    neighbor = {"_name": "Neighbor", "spairport_signal_noise": "-40 dBm / -96 dBm"}
    info = wifi_cmd._new_info()
    wifi_cmd._fill_from_profiler_json(info, _profiler_json(neighbor=neighbor))
    assert info["rssi"] == -63


def test_macos_json_redacted(monkeypatch):
    """系统打码时不能把 <redacted> 当网络名，且要提示开定位权限."""
    payload = _profiler_json(ssid="<redacted>")
    shim_run_cmd(monkeypatch, wifi_cmd, [
        ("SPAirPortDataType", payload), ("networksetup", None)])
    info = wifi_cmd._macos_wifi()
    assert info["ssid"] is None
    assert "定位" in info["note"]


def test_macos_json_not_connected(monkeypatch):
    """没连 Wi-Fi 时给出可理解的提示，而不是五个"未知"就完事."""
    payload = json.dumps({"SPAirPortDataType": [{"spairport_airport_interfaces": [
        {"_name": "en0", "spairport_status_information": "spairport_status_off"}]}]})
    shim_run_cmd(monkeypatch, wifi_cmd, [
        ("SPAirPortDataType", payload), ("networksetup", None)])
    info = wifi_cmd._macos_wifi()
    assert (info["ssid"], info["rssi"]) == (None, None)
    assert "没有连上" in info["note"]


@pytest.mark.parametrize("token,expect", [
    ("spairport_security_mode_wpa2_personal", "WPA2 Personal"),
    ("spairport_security_mode_wpa2_personal_mixed", "WPA2 Personal 混合"),
    ("spairport_security_mode_none", "开放（无加密）"),
    (None, None),
])
def test_macos_security_name(token, expect):
    assert wifi_cmd._macos_security_name(token) == expect


NETSH_CN = """
接口 WLAN 的配置

    名称                   : WLAN
    描述                   : Intel(R) Wi-Fi 6E AX211 160MHz
    状态                   : 已连接
    SSID                   : MyHome-5G
    BSSID                  : 3c:37:86:12:34:56
    无线电类型             : 802.11ax
    身份验证               : WPA2-个人
    信道                   : 149
    接收速率(Mbps)         : 866.7
    信号                   : 78%
"""


def test_windows_netsh_chinese(monkeypatch):
    """中文系统的 netsh 输出（信号是百分比，要换算成 dBm 才能和评分表对齐）."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, wifi_cmd, [("netsh", NETSH_CN)])
    info = wifi_cmd._windows_wifi()
    assert (info["ssid"], info["rssi"], info["channel"], info["bssid"],
            info["security"], info["rate"]) == (
        "MyHome-5G", -61, "149", "3c:37:86:12:34:56", "WPA2-个人", "866.7 Mbps")


def test_windows_netsh_disconnected(monkeypatch):
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, wifi_cmd, [("netsh", (
        "    Name                   : Wi-Fi\n"
        "    State                  : disconnected\n"))])
    info = wifi_cmd._windows_wifi()
    assert (info["ssid"], info["rssi"]) == (None, None)
    assert "没有连上" in info["note"]


def test_windows_no_adapter(monkeypatch):
    """没有无线网卡（或 WLAN 服务没启动）时要说清楚原因."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, wifi_cmd, [("netsh", "There is no wireless interface on the system.\n")])
    info = wifi_cmd._windows_wifi()
    assert (info["ssid"], info["rssi"]) == (None, None)
    assert "没有无线网卡" in info["note"]


NMCLI = ("eno1:no-network:0:0:--\n"
         "*:MyWiFi\\:5G:78:149:WPA2\n"   # 字段里的冒号会转义成 \:
         "other:Neighbor:40:6:WPA1\n")


def test_linux_nmcli(monkeypatch):
    """nmcli -t 的输出按未转义的冒号切分，IN-USE 为 * 的那行才是当前网络."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, wifi_cmd, [("nmcli", NMCLI), ("iw dev", None)])
    info = wifi_cmd._linux_wifi()
    assert (info["ssid"], info["rssi"], info["channel"], info["security"]) == (
        "MyWiFi:5G", -61, "149", "WPA2")


IW_LINK = """Connected to 3c:37:86:12:34:56 (on wlan0)
\tSSID: MyWiFi
\tfreq: 5745
\tsignal: -58 dBm
\ttx bitrate: 866.7 MBit/s
"""


def test_linux_iw_link(monkeypatch):
    """iw 只给中心频率，要自己换算成信道号."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, wifi_cmd, [
        ("nmcli", None),
        ("iw dev wlan0 link", IW_LINK),
        ("iw dev", "Interface wlan0\n"),
    ])
    info = wifi_cmd._linux_wifi()
    assert (info["ssid"], info["rssi"], info["channel"], info["bssid"], info["rate"]) == (
        "MyWiFi", -58, "149", "3c:37:86:12:34:56", "866.7 Mbps")


PROC_WIRELESS = (
    "Inter-| sta-|   Quality        |   Discarded packets               | Missed | WE\n"
    " face | tus | link level noise |  nwid  crypt   frag  retry   misc | beacon | 22\n"
    " wlan0: 0000   54.  -56.  -256.        0      0      0      0        0        0\n")


def test_linux_proc_wireless(monkeypatch):
    """没有 nmcli/iw 时读 /proc/net/wireless（有 level 但没有 SSID，用 iwgetid 补）."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, wifi_cmd, [
        ("nmcli", None), ("iwgetid", "MyWiFi\n"), ("iw dev", None)])
    fake_files(monkeypatch, {"/proc/net/wireless": PROC_WIRELESS})
    info = wifi_cmd._linux_wifi()
    assert (info["ssid"], info["rssi"]) == ("MyWiFi", -56)


@pytest.mark.parametrize("text,expect_rssi", [
    # 老驱动给质量值：旧实现直接把 60 当成 +60 dBm，弱信号会被判成满格
    ('wlan0     IEEE 802.11  ESSID:"MyWiFi"\n          Signal level=60/100  Noise level=-95 dBm\n', -70),
    # 标准 dBm 写法
    ('wlan0     IEEE 802.11  ESSID:"MyWiFi"\n          Signal level=-59 dBm\n', -59),
])
def test_linux_iwconfig(monkeypatch, text, expect_rssi):
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, wifi_cmd, [
        ("nmcli", None), ("iw dev", None), ("iwconfig", text)])
    info = wifi_cmd._linux_wifi()
    assert (info["ssid"], info["rssi"]) == ("MyWiFi", expect_rssi)


def test_linux_no_tools(monkeypatch):
    """一个无线工具都没有时：不编造信号值，给出可理解的提示."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, wifi_cmd, [])
    info = wifi_cmd._linux_wifi()
    assert (info["ssid"], info["rssi"]) == (None, None)
    assert info["note"] is not None


def test_no_signal_no_score():
    """拿不到信号强度时不评分（旧实现用 -100 dBm 兜底，会打出一条假评级）."""
    assert wifi_cmd.score_signal(None) == (None, None)


@pytest.mark.parametrize("rssi,expect_pct", [
    (-30, 100.0),   # 强
    (-70, 60.0),    # 中
    (-90, 5.0),     # 弱：评分表下限
])
def test_score_signal(rssi, expect_pct):
    assert wifi_cmd.score_signal(rssi)[0] == expect_pct


@pytest.mark.parametrize("freq,expect", [
    (2412, 1), (2437, 6), (2484, 14), (5180, 36), (5745, 149), (5955, 1), (0, None),
])
def test_freq_to_channel(freq, expect):
    assert wifi_cmd._freq_to_channel(freq) == expect


def test_split_escaped():
    """nmcli -t 用 ':' 分隔字段，字段内的 ':' 会转义，不能直接 split."""
    assert wifi_cmd._split_escaped("*:MyWiFi\\:5G:78:149:WPA2") == [
        "*", "MyWiFi:5G", "78", "149", "WPA2"]
