"""port 命令的解析：三种系统工具的输出格式，以及工具缺失时的诚实表现."""
from helpers import fake_files, set_platform, shim_run_cmd
from wocli.commands import port

LSOF = """COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
mysqld     1111 woju   19u  IPv4 0xc185ef26d73aab3d      0t0  TCP 127.0.0.1:33060 (LISTEN)
postgres  19992 woju    7u  IPv6 0x805de3e4d764fd55      0t0  TCP [::1]:5432 (LISTEN)
"""


def test_lsof_parse():
    assert port._ports_from_lsof(LSOF) == [("33060", "mysqld"), ("5432", "postgres")]


def test_macos_netstat_parse():
    """netstat 用点号分隔地址，且要 root 才带进程名，所以进程名用 - 占位."""
    text = ("tcp4       0      0  127.0.0.1.3306         *.*                    LISTEN\n"
            "tcp4       0      0  127.0.0.1.49612        *.*                    ESTABLISHED\n")
    assert port._ports_from_macos_netstat(text) == [("3306", "-")]


SS = ('State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n'
      'LISTEN 0      128          0.0.0.0:22        0.0.0.0:*     users:(("sshd",pid=800,fd=3))\n'
      'LISTEN 0      128             [::]:80           [::]:*     \n')


def test_ss_parse():
    """有权限的进程能看到名字，看不到的用 - 占位."""
    assert port._ports_from_ss(SS) == [("22", "sshd"), ("80", "-")]


def test_proc_net_tcp_parse(monkeypatch):
    """/proc/net/tcp 的端口是 16 进制，只有 state 0A（LISTEN）算数."""
    fake_files(monkeypatch, {"/proc/net/tcp": (
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid\n"
        "   0: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0\n"
        "   1: 0100007F:0CEA 00000000:0000 0A 00000000:00000000 00:00000000 00000000     0\n"
        "   2: 0100007F:1F90 00000000:0000 01 00000000:00000000 00:00000000 00000000     0\n"
        "   3: 0100007F:1F91 00000000:0000 06 00000000:00000000 00:00000000 00000000     0\n"),
        "/proc/net/tcp6": ""})
    assert port._ports_from_proc_net_tcp() == [("22", "-"), ("3306", "-")]


NETSTAT = """
活动连接

  协议  本地地址          外部地址        状态           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1108
  TCP    127.0.0.1:3306         0.0.0.0:0              LISTENING       5678
  TCP    [::]:445               [::]:0                 LISTENING       4
  UDP    0.0.0.0:500            *:*                                    1108
"""

TASKLIST = ('"svchost.exe","1108","Services","0","10,000 K"\n'
            '"mysqld.exe","5678","Console","1","80,000 K"\n'
            '"System","4","Services","0","100 K"\n')


def test_windows_ports(monkeypatch):
    """一次 tasklist 建出 PID 到进程名的表，端口行只认 LISTENING."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, port, [("netstat", NETSTAT), ("tasklist", TASKLIST)])
    assert port.get_ports_windows() == [
        ("135", "svchost.exe"), ("3306", "mysqld.exe"), ("445", "System")]


def test_windows_tools_missing(monkeypatch):
    """工具跑不起来时返回 None，上层才能说"没法获取"而不是"没有端口"."""
    set_platform(monkeypatch, "Windows")
    shim_run_cmd(monkeypatch, port, [])
    assert port.get_ports_windows() is None


def test_macos_tools_missing(monkeypatch):
    set_platform(monkeypatch, "Darwin")
    shim_run_cmd(monkeypatch, port, [])
    assert port.get_ports_macos() is None


def test_linux_falls_back_to_proc(monkeypatch):
    """Linux 的 ss 和 netstat 都没有时，读 /proc/net/tcp 兜底."""
    set_platform(monkeypatch, "Linux")
    shim_run_cmd(monkeypatch, port, [])
    fake_files(monkeypatch, {"/proc/net/tcp": (
        "  sl  local_address rem_address   st\n"
        "   0: 00000000:0016 00000000:0000 0A\n"), "/proc/net/tcp6": ""})
    assert port.get_ports_linux() == [("22", "-")]
