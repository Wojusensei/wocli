"""wocli ip - Show network information."""

import ipaddress
import platform
import socket
import struct
import time
import urllib.request

from wocli.utils import run_cmd

UNKNOWN = "未获取到"

# 公网 IP 查询源：按顺序试，任一源给出合法地址就返回。
# 国内网络经常直连不上 ipify，所以 icanhazip 放前面；每个源单独限时，
# 整体还有一份预算，断网时不会把命令拖成十几个源累加的十几秒。
PUBLIC_IP_SOURCES = {
    4: ("https://ipv4.icanhazip.com",
        "https://api.ipify.org",
        "https://ipinfo.io/ip",
        "https://ifconfig.me/ip"),
    6: ("https://ipv6.icanhazip.com",
        "https://api6.ipify.org",
        "https://ident.me"),
}
PUBLIC_IP_TIMEOUT = 4
PUBLIC_IP_BUDGET = 8


def _udp_source_ip(family, target):
    """UDP socket「连」到远端地址但不发包：内核按路由表挑源地址，getsockname 拿到的就是本机地址."""
    sock = None
    try:
        sock = socket.socket(family, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        sock.connect((target, 80))
        return sock.getsockname()[0]
    except Exception:
        return None
    finally:
        if sock is not None:
            sock.close()


def _usable_ip(text, family):
    """判断是否是「能代表本机网络」的地址：排掉回环、链路本地(169.254/fe80)、未指定地址."""
    try:
        addr = ipaddress.ip_address(text)
    except ValueError:
        return False
    if addr.version != family:
        return False
    return not (addr.is_loopback or addr.is_link_local or addr.is_unspecified)


def _token_after(text, key):
    """取命令行输出里 key 后面的第一个词，例如 "via 192.168.1.1 dev en0" 取 via 后的网关."""
    if not text:
        return None
    fields = text.split()
    for index, field in enumerate(fields):
        if field == key and index + 1 < len(fields):
            return fields[index + 1]
    return None


def _value_after(text, key):
    """取 "gateway: 10.0.0.1" 这类冒号行里的值，返回去空白后的整段."""
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(key):
            value = stripped[len(key):].strip()
            if value:
                return value
    return None


# ---------- 内网 IPv4 ----------

def _ipv4_from_ifconfig(text):
    """解析 ifconfig：取第一个非 lo 接口的 inet（离线、没有默认路由时的兜底）."""
    iface = ""
    for line in (text or "").splitlines():
        if line[:1].strip() and ":" in line:
            iface = line.split(":", 1)[0]
        elif "inet " in line and not iface.startswith("lo"):
            candidate = line.split("inet ", 1)[1].split()[0]
            if _usable_ip(candidate, 4):
                return candidate
    return None


def _ipv4_from_ipconfig(text):
    """解析 Windows ipconfig，中英文关键词都要认（受支持的系统里没有语言无关的等价输出）."""
    if not text:
        return None
    labels = ("IPv4 Address", "IPv4 地址", "IP Address", "IP 地址")
    for line in text.splitlines():
        if ":" not in line or not any(label in line for label in labels):
            continue
        value = line.split(":", 1)[1].strip()
        # 中文系统会带 "(首选)"，英文带 "(Preferred)"，取括号前那段
        candidate = value.split("(")[0].split("（")[0].strip()
        if _usable_ip(candidate, 4):
            return candidate
    return None


def _ipv4_from_ip_addr(text):
    """解析 ip -4 -o addr show scope global 的行：3: en0    inet 192.168.1.5/24 brd ..."""
    for line in (text or "").splitlines():
        fields = line.split()
        if len(fields) >= 4 and fields[2] == "inet":
            candidate = fields[3].split("/")[0]
            if _usable_ip(candidate, 4):
                return candidate
    return None


def get_local_ip():
    """取内网 IPv4：先用路由选源地址，再按平台枚举网卡，最后退回解析主机名."""
    candidate = _udp_source_ip(socket.AF_INET, "8.8.8.8")
    if candidate and _usable_ip(candidate, 4):
        return candidate

    system = platform.system()
    if system == "Darwin":
        candidate = _ipv4_from_ifconfig(run_cmd(["ifconfig"]))
    elif system == "Windows":
        out = run_cmd([
            "powershell", "-NoProfile", "-Command",
            "$a = Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '127.*' "
            "-and $_.IPAddress -notlike '169.254.*' } | "
            "Sort-Object InterfaceMetric | Select-Object -First 1; "
            "if ($a) { $a.IPAddress }",
        ], timeout=10)
        candidate = (out or "").strip() or None
        if candidate and not _usable_ip(candidate, 4):
            candidate = _ipv4_from_ipconfig(run_cmd(["ipconfig"]))
    else:
        # hostname -I 一次给出全部地址，比逐个网卡探测省事
        out = run_cmd(["hostname", "-I"])
        for item in (out or "").split():
            if _usable_ip(item, 4):
                candidate = item
                break
        else:
            candidate = _ipv4_from_ip_addr(
                run_cmd(["ip", "-4", "-o", "addr", "show", "scope", "global"])
            )
    if candidate:
        return candidate

    # 离线且网卡枚举也失败时，试试主机名解析（/etc/hosts 里有映射就能中）
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidate = info[4][0]
            if _usable_ip(candidate, 4):
                return candidate
    except Exception:
        pass
    return UNKNOWN


# ---------- 内网 IPv6 ----------

def _ipv6_from_proc_net():
    """Linux：/proc/net/if_inet6 里 scope 00 是全局地址、20 是链路本地，无需 root 也不需要 ip 命令."""
    globals_found = []
    locals_found = []
    try:
        with open("/proc/net/if_inet6", "r") as handle:
            rows = handle.read().splitlines()
    except OSError:
        return None
    for row in rows:
        fields = row.split()
        if len(fields) < 6:
            continue
        try:
            addr = ipaddress.IPv6Address(int(fields[0], 16))
        except ValueError:
            continue
        if addr == ipaddress.IPv6Address("::1"):
            continue
        if addr.is_link_local:
            locals_found.append(str(addr))
        else:
            globals_found.append(str(addr))
    if globals_found:
        return globals_found[0]
    return locals_found[0] if locals_found else None


def _ipv6_from_ifconfig(text):
    """解析 ifconfig 的 inet6 行：优先稳定的 autoconf 地址，其次是临时地址，最后才是 fe80."""
    stable = temporary = link = None
    for line in (text or "").splitlines():
        if "inet6" not in line:
            continue
        candidate = line.split("inet6", 1)[1].split()[0].split("%")[0]
        try:
            addr = ipaddress.IPv6Address(candidate)
        except ValueError:
            continue
        if addr.is_loopback:
            continue
        if addr.is_link_local:
            link = link or candidate
        elif "temporary" in line:
            temporary = temporary or candidate
        else:
            stable = stable or candidate
    return stable or temporary or link


def get_ipv6():
    """取内网 IPv6：全局地址优先，实在只有 fe80 才报链路本地."""
    candidate = _udp_source_ip(socket.AF_INET6, "2001:4860:4860::8888")
    if candidate and _usable_ip(candidate, 6):
        return candidate

    system = platform.system()
    if system == "Darwin":
        candidate = _ipv6_from_ifconfig(run_cmd(["ifconfig"]))
    elif system == "Windows":
        out = run_cmd([
            "powershell", "-NoProfile", "-Command",
            "$a = Get-NetIPAddress -AddressFamily IPv6 | "
            "Where-Object { $_.IPAddress -ne '::1' "
            "-and $_.IPAddress -notlike 'fe80*' } | "
            "Sort-Object InterfaceMetric | Select-Object -First 1; "
            "if ($a) { $a.IPAddress }",
        ], timeout=10)
        candidate = (out or "").strip() or None
        if candidate and not _usable_ip(candidate, 6):
            candidate = None
    else:
        candidate = _ipv6_from_proc_net()
        if not candidate:
            candidate = _ipv6_from_ifconfig(
                run_cmd(["ip", "-6", "addr", "show", "scope", "global"])
            )
    return candidate or UNKNOWN


# ---------- 默认网关 ----------

def _gateway_from_netstat(text):
    """netstat -rn 兜底：IPv4 表在 Internet6 前面，但还是要确认取到的是 IPv4 网关."""
    for line in (text or "").splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[0] == "default" and _usable_ip(fields[1], 4):
            netif = fields[-1] if len(fields) > 3 else None
            return fields[1], netif
    return None, None


def _gateway_from_proc_net_route():
    """Linux 没有 ip 命令时的兜底：/proc/net/route 的网关是 16 进制小端，要倒过来解."""
    try:
        with open("/proc/net/route", "r") as handle:
            rows = handle.read().splitlines()[1:]
    except OSError:
        return None, None
    for row in rows:
        fields = row.split()
        if len(fields) >= 3 and fields[1] == "00000000":
            try:
                gateway = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
            except (ValueError, struct.error, OSError):
                continue
            if gateway != "0.0.0.0":
                return gateway, fields[0]
    return None, None


def _gateway_macos():
    # route get 比解析 netstat 表格准：直接给出正在生效的那条默认路由
    out = run_cmd(["route", "-n", "get", "default"], timeout=5)
    gateway = _value_after(out, "gateway:")
    if gateway:
        return gateway, _value_after(out, "interface:")
    return _gateway_from_netstat(run_cmd(["netstat", "-rn"]))


def _gateway_linux():
    for cmd in (["ip", "route", "get", "1.1.1.1"], ["ip", "route", "show", "default"]):
        out = run_cmd(cmd, timeout=5)
        gateway = _token_after(out, "via")
        if gateway:
            return gateway, _token_after(out, "dev")
    return _gateway_from_proc_net_route()


def _gateway_windows():
    # Get-NetRoute 输出不随系统语言变；ipconfig 的 "默认网关" 只能当回退
    out = run_cmd([
        "powershell", "-NoProfile", "-Command",
        "$r = Get-NetRoute -DestinationPrefix 0.0.0.0/0 | "
        "Sort-Object RouteMetric | Select-Object -First 1; "
        "if ($r) { '{0}|{1}' -f $r.NextHop, $r.InterfaceAlias }",
    ], timeout=10)
    text = (out or "").strip()
    if "|" in text:
        gateway, _, alias = text.partition("|")
        return gateway.strip() or None, alias.strip() or None
    if text and _usable_ip(text, 4):
        return text, None

    out = run_cmd(["ipconfig"])
    for line in (out or "").splitlines():
        if ":" not in line:
            continue
        if "Default Gateway" in line or "默认网关" in line:
            candidate = line.split(":", 1)[1].strip()
            if _usable_ip(candidate, 4):
                return candidate, None
    return None, None


def get_gateway():
    """返回 (默认网关, 出口网卡)，取不到给 (None, None)."""
    system = platform.system()
    if system == "Darwin":
        return _gateway_macos()
    if system == "Windows":
        return _gateway_windows()
    return _gateway_linux()


def get_gateway6():
    """取 IPv6 默认网关：通常是 fe80::1%en0 这种链路本地地址，没有 IPv6 就返回 None."""
    system = platform.system()
    if system == "Darwin":
        out = run_cmd(["route", "-n", "get", "-inet6", "default"], timeout=5)
        return _value_after(out, "gateway:")
    if system == "Windows":
        out = run_cmd([
            "powershell", "-NoProfile", "-Command",
            "$r = Get-NetRoute -AddressFamily IPv6 -DestinationPrefix ::/0 | "
            "Sort-Object RouteMetric | Select-Object -First 1; "
            "if ($r) { $r.NextHop }",
        ], timeout=10)
        return (out or "").strip() or None
    return _token_after(
        run_cmd(["ip", "-6", "route", "show", "default"], timeout=5), "via"
    )


# ---------- 公网 IP ----------

def _http_text(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "wocli"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        # 只读前 200 字节：这些接口正常只回一行地址，拒绝被重定向到的大页面拖住
        return response.read(200).decode("utf-8", "replace")


def get_public_ip(version):
    """按顺序试各查询源，返回第一个版本号匹配的合法地址，全都失败返回 None.

    逐个校验版本号是必要的：ifconfig.me 这类双栈接口会跟着连接走 IPv6，
    不校验的话「公网 IPv4」那一行会印出一个 v6 地址。
    """
    deadline = time.monotonic() + PUBLIC_IP_BUDGET
    for url in PUBLIC_IP_SOURCES[version]:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break
        try:
            text = _http_text(url, min(PUBLIC_IP_TIMEOUT, remain)).strip()
        except Exception:
            continue
        candidate = text.split()[0] if text else ""
        try:
            addr = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if addr.version == version:
            return str(addr)
    return None


def run():
    local_ip = get_local_ip()
    ipv6 = get_ipv6()
    gateway, gateway_iface = get_gateway()
    gateway6 = get_gateway6()

    print()
    print(f"  内网 IPv4：{local_ip}")
    print(f"  内网 IPv6：{ipv6}")
    iface_hint = f"（{gateway_iface}）" if gateway_iface else ""
    print(f"  默认网关：{gateway or UNKNOWN}{iface_hint}")
    if gateway6:
        print(f"  IPv6 网关：{gateway6}")

    public_v4 = get_public_ip(4)
    print(f"  公网 IPv4：{public_v4 or UNKNOWN}")
    # 本机没有全局 IPv6 时就不去问 v6 接口了，省一次必然超时的请求
    try:
        has_global_v6 = not ipaddress.ip_address(ipv6).is_link_local
    except ValueError:
        has_global_v6 = False
    if has_global_v6:
        print(f"  公网 IPv6：{get_public_ip(6) or UNKNOWN}")
    print()
