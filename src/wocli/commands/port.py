"""wocli port - 查看端口占用."""

import csv
import io
import platform
import re

from wocli.utils import run_cmd


def _split_addr_port(addr):
    """从 lsof/ss 的地址串里取端口：127.0.0.1:3306、*:8787、[::1]:5432 都要认."""
    if ":" not in addr:
        return None
    return addr.rsplit(":", 1)[1]


def _ports_from_lsof(text):
    ports = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        port = _split_addr_port(parts[8])
        if port:
            ports.append((port, parts[0]))
    return ports


def _ports_from_macos_netstat(text):
    """netstat -an -p tcp 的监听行用点号分隔地址：127.0.0.1.3306，且要 root 才带进程名."""
    ports = []
    for line in (text or "").splitlines():
        if "LISTEN" not in line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        port = parts[3].rsplit(".", 1)[-1]
        if port.isdigit():
            ports.append((port, "-"))
    return ports


def _ports_from_ss(text):
    """ss -tlnp 一行：LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=1,fd=3))"""
    ports = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        port = _split_addr_port(parts[3])
        if not port:
            continue
        # 没权限看别的用户进程时 users: 段会缺失，退回 "-"
        match = re.search(r'users:\(\("([^"]+)"', line)
        ports.append((port, match.group(1) if match else "-"))
    return ports


def _ports_from_proc_net_tcp():
    """连 ss/netstat 都没有时的兜底：/proc/net/tcp 里 state 0A 就是 LISTEN，端口是 16 进制."""
    ports = []
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, "r") as handle:
                rows = handle.read().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            fields = row.split()
            if len(fields) < 4 or fields[3] != "0A" or ":" not in fields[1]:
                continue
            port = int(fields[1].rsplit(":", 1)[1], 16)
            ports.append((str(port), "-"))
    return ports


def _windows_process_names():
    """一次 tasklist 拿全部进程名.

    旧实现给每个 PID 单独起一次 tasklist，端口多的时候要好几秒。
    """
    names = {}
    text = run_cmd(["tasklist", "/FO", "CSV", "/NH"], timeout=20)
    if not text:
        return names
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2 and row[1].strip().isdigit():
            names[row[1].strip()] = row[0]
    return names


def get_ports_macos():
    text = run_cmd(["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"], timeout=20)
    if text is not None:
        return _ports_from_lsof(text)
    # 没装 lsof（或者被安全策略拦了）时退回 netstat，代价是没有进程名
    text = run_cmd(["netstat", "-an", "-p", "tcp"], timeout=20)
    if text is not None:
        return _ports_from_macos_netstat(text)
    return None


def get_ports_windows():
    text = run_cmd(["netstat", "-ano"], timeout=20)
    if text is None:
        return None
    names = _windows_process_names()
    ports = []
    for line in text.splitlines():
        if "LISTENING" not in line.upper():
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        port = _split_addr_port(parts[1])
        if port:
            ports.append((port, names.get(parts[-1], parts[-1])))
    return ports


def get_ports_linux():
    text = run_cmd(["ss", "-tlnp"], timeout=20)
    if text is not None:
        return _ports_from_ss(text)
    text = run_cmd(["netstat", "-tlnp"], timeout=20)
    if text is not None:
        return _ports_from_ss(text)
    return _ports_from_proc_net_tcp()


def run():
    system = platform.system()
    if system == "Darwin":
        ports = get_ports_macos()
    elif system == "Windows":
        ports = get_ports_windows()
    else:
        ports = get_ports_linux()

    # None 和空列表要分开：一个系统工具都跑不起来时不能说"没有端口"
    if ports is None:
        print("\n  无法获取端口占用（系统里缺少 lsof / ss / netstat 命令）。\n")
        return
    if not ports:
        print("\n  没有发现监听端口。\n")
        return

    print()
    print("  端口占用情况：")
    print()
    seen = set()
    for port, proc in ports:
        if port not in seen:
            seen.add(port)
            print(f"  {port:<8} {proc}")
    print()
