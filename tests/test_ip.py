"""ip 命令的跨平台解析：内网地址、网关、公网地址校验."""
import pytest

from helpers import fake_files, set_platform, shim_run_cmd
from wocli.commands import ip


@pytest.mark.parametrize("text,expect", [
    # 多个网卡时取第一个非 lo 的 IPv4
    ("lo0: flags\n\tinet 127.0.0.1 netmask 0xff000000\n"
     "en0: flags\n\tinet 10.255.47.248 netmask 0xffffff00\n"
     "utun0: flags\n\tinet 192.168.64.1 netmask 0xffffff00\n", "10.255.47.248"),
    # 只有回环时不能把 127.0.0.1 当内网地址
    ("lo0: flags\n\tinet 127.0.0.1 netmask 0xff000000\n", None),
    # 链路本地（169.254/16）不算内网地址
    ("en0: flags\n\tinet 169.254.10.20 netmask 0xffff0000\n", None),
])
def test_ipv4_from_ifconfig(text, expect):
    assert ip._ipv4_from_ifconfig(text) == expect


@pytest.mark.parametrize("text,expect", [
    ("以太网适配器 以太网:\n\n"
     "   IPv4 地址 . . . . . . . . . . . . : 192.168.1.23(首选)\n", "192.168.1.23"),
    ("   IPv4 Address. . . . . . . . . . . : 10.0.0.8(Preferred)\n", "10.0.0.8"),
    # 网关不能被当成 IPv4 地址
    ("   默认网关 . . . . . . . . . . . . : 192.168.1.1\n", None),
])
def test_ipv4_from_ipconfig(text, expect):
    assert ip._ipv4_from_ipconfig(text) == expect


def test_ipv4_from_ip_addr():
    """ip -4 -o addr show scope global 的行格式."""
    text = ("2: eth0    inet 192.168.1.5/24 brd 192.168.1.255 scope global dynamic eth0\n"
            "3: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\n")
    assert ip._ipv4_from_ip_addr(text) == "192.168.1.5"


@pytest.mark.parametrize("value,family,expect", [
    ("192.168.1.5", 4, True),
    ("127.0.0.1", 4, False),
    ("169.254.10.20", 4, False),
    ("240e:467:4da:59:bf23:fc4b:fdf0:3c9e", 6, True),
    ("::1", 6, False),
    ("fe80::1", 6, False),
    ("240e:467:4da:59:bf23:fc4b:fdf0:3c9e", 4, False),
    ("not-an-ip", 4, False),
])
def test_usable_ip(value, family, expect):
    assert ip._usable_ip(value, family) is expect


@pytest.mark.parametrize("content,expect", [
    # 全局地址优先，链路本地和回环都要排掉
    ("00000000000000000000000000000001 01 80 10 80       lo\n"
     "fe800000000000000000000000000001 02 40 20 80     eth0\n"
     "240e046704da0059bf23fc4bfdf03c9e 02 40 00 00     eth0\n",
     "240e:467:4da:59:bf23:fc4b:fdf0:3c9e"),
    # 只有链路本地时如实报 fe80，而不是返回"未知"
    ("fe800000000000000000000000000001 02 40 20 80 eth0\n", "fe80::1"),
    # 只有回环就当作没有 IPv6
    ("00000000000000000000000000000001 01 80 10 80 lo\n", None),
])
def test_ipv6_from_proc_net(monkeypatch, content, expect):
    fake_files(monkeypatch, {"/proc/net/if_inet6": content})
    assert ip._ipv6_from_proc_net() == expect


def test_gateway_from_proc_net_route(monkeypatch):
    """没有 ip 命令时的兜底：Destination 00000000 是默认路由，网关是 16 进制小端."""
    fake_files(monkeypatch, {"/proc/net/route": (
        "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
        "eth0\t00000000\t0101A8C0\t0003\t0\t0\t0\t00000000\t0\t0\t0\n")})
    assert ip._gateway_from_proc_net_route() == ("192.168.1.1", "eth0")


def test_gateway_from_proc_net_route_missing(monkeypatch):
    fake_files(monkeypatch, {"/proc/net/route": "Iface\tDestination\tGateway\tFlags\n"})
    assert ip._gateway_from_proc_net_route() == (None, None)


def test_gateway_linux(monkeypatch):
    """ip route get 的输出里 via 后面是网关、dev 后面是出口网卡."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, ip, [
        ("ip route get", "1.1.1.1 via 192.168.1.1 dev wlan0 src 192.168.1.5 uid 1000\n"),
    ])
    assert ip._gateway_linux() == ("192.168.1.1", "wlan0")


def test_gateway_linux_without_ip_command(monkeypatch):
    """精简系统里没有 ip 命令时，回退到 /proc/net/route."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, ip, [])
    fake_files(monkeypatch, {"/proc/net/route": (
        "Iface\tDestination\tGateway \tFlags\n"
        "eth0\t00000000\t0101A8C0\t0003\n")})
    assert ip._gateway_linux() == ("192.168.1.1", "eth0")


def test_gateway_windows(monkeypatch):
    """Get-NetRoute 的输出不随系统语言变，网关和网卡别名一起取回."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, ip, [("Get-NetRoute -DestinationPrefix", "192.168.1.1|WLAN\n")])
    assert ip._gateway_windows() == ("192.168.1.1", "WLAN")


def test_gateway_windows_ipconfig_fallback(monkeypatch):
    """老系统没有 NetTCPIP 模块，退回解析 ipconfig（中英文关键词都要认）."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, ip, [("ipconfig", (
        "以太网适配器 以太网:\n"
        "   默认网关. . . . . . . . . . . . . : 192.168.1.1\n"))])
    assert ip._gateway_windows() == ("192.168.1.1", None)


def _fake_http(monkeypatch, answers):
    """answers 里没列出的 URL 一律抛异常，模拟这个源连不通."""
    def fake(url, timeout):
        if url in answers:
            return answers[url]
        raise OSError("connection refused")
    monkeypatch.setattr(ip, "_http_text", fake)


def test_public_ip_skips_html(monkeypatch):
    """查询源返回整页 HTML 时要跳过，不能把 HTML 印成公网 IP."""
    monkeypatch.setattr(ip, "PUBLIC_IP_SOURCES", {4: ("https://a", "https://b")})
    _fake_http(monkeypatch, {"https://a": "<html><body>hello</body></html>",
                             "https://b": "120.32.249.179\n"})
    assert ip.get_public_ip(4) == "120.32.249.179"


def test_public_ip_rejects_wrong_family(monkeypatch):
    """双栈源会跟着连接返回 v6 地址，问 v4 时这种结果必须丢掉."""
    monkeypatch.setattr(ip, "PUBLIC_IP_SOURCES", {4: ("https://dual",)})
    _fake_http(monkeypatch, {"https://dual": "240e:467:4da:59:bf23:fc4b:fdf0:3c9e"})
    assert ip.get_public_ip(4) is None


def test_public_ip_all_sources_down(monkeypatch):
    """断网时返回 None（由上层显示"未获取到"），不能抛异常也不能编地址."""
    monkeypatch.setattr(ip, "PUBLIC_IP_SOURCES", {4: ("https://a", "https://b")})
    _fake_http(monkeypatch, {})
    assert ip.get_public_ip(4) is None
