"""wocli chat - 局域网终端聊天"""
import platform
import re
import socket
import sys
import threading
import time

from wocli.utils import run_cmd

DEFAULT_PORT = 52020
MAGIC = b"WOCLI-CHAT/1"
# 服务端等对方接入的时长。原来只有 60 秒：对方看 IP、输地址、确认防火墙，
# 超过一分钟很常见，服务端先退出后客户端只能收到 connection refused。
ACCEPT_WAIT_SECONDS = 600
# 客户端的重试窗口。房间可能比自己晚建好，只试一次就会误报失败。
CONNECT_RETRY_SECONDS = 30
PROGRESS_INTERVAL = 30


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "未知"


def _extra_local_ips():
    """多网卡时多列几个地址：VPN、docker0 的地址对方是连不上的."""
    system = platform.system()
    if system == "Linux":
        return (run_cmd(["hostname", "-I"], timeout=5) or "").split()
    if system == "Darwin":
        text = run_cmd(["ifconfig"], timeout=5) or ""
        return re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", text)
    text = run_cmd([
        "powershell", "-NoProfile", "-Command",
        "(Get-NetIPAddress -AddressFamily IPv4).IPAddress",
    ], timeout=10) or ""
    return text.split()


def local_ip_candidates():
    """本机可能被对方连上的 IPv4 列表（去掉回环和链路本地，去重）."""
    candidates = []
    primary = get_local_ip()
    if primary != "未知":
        candidates.append(primary)
    for ip in _extra_local_ips():
        ip = ip.strip()
        if not ip or ip in candidates:
            continue
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        candidates.append(ip)
    return candidates or ["未知"]


def read_line(sock, limit=256):
    """逐字节读一行（握手用），对端关闭、超时或超长返回 None.

    逐字节读是有意的：recv(1024) 可能多读走后面本该属于聊天内容的数据。
    """
    buf = b""
    while b"\n" not in buf:
        try:
            data = sock.recv(1)
        except OSError:
            return None
        if not data:
            return None
        buf += data
        if len(buf) > limit:
            return None
    return buf.split(b"\n", 1)[0]


def handshake_send(sock):
    """客户端一侧的握手：打招呼并确认对方回了同样的标记."""
    try:
        sock.sendall(MAGIC + b"\n")
        return read_line(sock) == MAGIC
    except OSError:
        return False


def handshake_recv(sock):
    """服务端一侧的握手：先收到标记，再回同样的标记."""
    if read_line(sock) != MAGIC:
        return False
    try:
        sock.sendall(MAGIC + b"\n")
        return True
    except OSError:
        return False


def wait_for_peer(server, wait_seconds=ACCEPT_WAIT_SECONDS):
    """等一个真正的 wocli chat 对端.

    连上来但握手不对的连接（端口扫描、别的程序、旧版本）回一句拒绝后继续等，
    不会再像以前那样把服务端唯一一次 accept 用掉、导致真正的人连不进来。
    """
    started = time.monotonic()
    deadline = started + wait_seconds
    next_hint = started + PROGRESS_INTERVAL
    while True:
        now = time.monotonic()
        if now >= deadline:
            return None
        if now >= next_hint:
            sys.stdout.write(f"\r  还在等…（已等 {int(now - started)} 秒）\033[K")
            sys.stdout.flush()
            next_hint = now + PROGRESS_INTERVAL
        server.settimeout(max(1.0, min(deadline - now, 5.0)))
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            return None
        conn.settimeout(5)
        if handshake_recv(conn):
            conn.settimeout(None)
            sys.stdout.write("\r\033[K")
            print(f"  对方已连接：{addr[0]}")
            return conn
        try:
            conn.sendall(b"WOCLI-CHAT/0\n")
        except OSError:
            pass
        conn.close()
        sys.stdout.write("\r\033[K")
        print(f"  忽略了 {addr[0]} 的连接：不是 wocli chat 对端（或版本不一致），继续等待")


def describe_error(exc):
    """把 connect 的错误翻成"下一步该看什么"."""
    if isinstance(exc, ConnectionRefusedError):
        return "对方的端口没有在监听：房间可能没建、已经等到超时退出，或端口不对"
    if isinstance(exc, socket.timeout):
        return "连接超时：IP 可能不对，或者被防火墙拦住了"
    if isinstance(exc, OSError) and exc.errno in (51, 65, 101, 113):
        return "网络不可达：IP 可能不是同一局域网里的地址"
    return str(exc)


def connect_to_peer(host, port, retry_seconds=CONNECT_RETRY_SECONDS):
    """连上对方并完成握手；对方房间还没建好时会在窗口内重试.

    返回 (socket, None) 或 (None, 失败原因)。
    """
    deadline = time.monotonic() + retry_seconds
    first_error = None
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect((host, port))
        except OSError as exc:
            sock.close()
            if first_error is None:
                first_error = exc
                print(f"  暂时连不上（{describe_error(exc)}）")
                print(f"  在 {retry_seconds} 秒内继续重试，请确认对方已经选 1 建好房间…")
            if time.monotonic() >= deadline:
                return None, first_error
            time.sleep(1)
            continue

        sock.settimeout(5)
        if handshake_send(sock):
            sock.settimeout(None)
            return sock, None
        sock.close()
        return None, RuntimeError(
            "连上了，但对端不是 wocli chat 房间（握手不匹配，也可能双方版本不一致）")


def receive_msg(sock, running):
    # 消息按 \n 分帧：recv 1024 可能截断长消息甚至截断 UTF-8 多字节字符，
    # 直接 decode 会抛 UnicodeDecodeError 让接收线程崩掉
    buf = b""
    while running[0]:
        try:
            data = sock.recv(1024)
            if not data:
                if running[0]:
                    sys.stdout.write("\n  连接已断开。\n")
                    sys.stdout.flush()
                    running[0] = False
                break
            buf += data
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                msg = raw.decode("utf-8", "replace")
                if msg.strip() == "/quit":
                    sys.stdout.write("\r\033[K  对方已退出聊天。\n")
                    sys.stdout.flush()
                    running[0] = False
                    return
                sys.stdout.write(f"\r\033[K  [对方] {msg}\n  > ")
                sys.stdout.flush()
        except OSError:
            if running[0]:
                sys.stdout.write("\n  连接已断开。\n")
                sys.stdout.flush()
                running[0] = False
            break


def run_server(port):
    print("\n  本机内网 IP：")
    for ip in local_ip_candidates():
        print(f"    {ip}")
    print(f"  端口：{port}")
    print("  把其中一个 IP 和端口告诉对方，对方选 2 加入房间。")
    print(f"  等待对方连接…（最多等 {max(1, ACCEPT_WAIT_SECONDS // 60)} 分钟）\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", port))
    except OSError as exc:
        print(f"  端口 {port} 用不了：{exc}")
        print("  可能是另一个没退出的 wocli chat 还占着它。")
        print(f"  关掉它，或换个端口：wocli chat --port {port + 1}")
        return None
    try:
        # 队列开大一点：杂连接不至于把 TCP 层的等待队列堵死
        server.listen(4)
        conn = wait_for_peer(server)
        if conn is None:
            print("\n  等待超时，没人连进来。\n")
            return None
        print("  开始聊天，输入 /quit 退出。\n")
        return conn
    finally:
        server.close()


def run_client(host, port):
    print(f"\n  正在连接 {host}:{port}…")
    conn, error = connect_to_peer(host, port)
    if conn is None:
        print(f"\n  加入房间失败：{error}\n")
        print("  按这个顺序排查：")
        print("    1. 对方是不是还停在「等待对方连接」（现在最多等 10 分钟）")
        print("    2. IP 是不是同一局域网的内网地址（对方会列出几个候选）")
        print(f"    3. 端口对不对（默认 {DEFAULT_PORT}，自定义端口写成 IP:端口）")
        print("    4. 防火墙有没有放行 wocli / Python\n")
        return None
    print("  已连接！")
    print("  开始聊天，输入 /quit 退出。\n")
    return conn


def chat_loop(sock, running):
    try:
        while running[0]:
            msg = input("  > ")
            if not msg.strip():
                continue
            if msg.strip() == "/quit":
                sock.sendall(b"/quit\n")
                running[0] = False
                break
            sock.sendall(msg.encode("utf-8") + b"\n")
    except (EOFError, KeyboardInterrupt):
        try:
            sock.sendall(b"/quit\n")
        except OSError:
            pass
        running[0] = False
    except OSError:
        print("\n  连接已断开。")
        running[0] = False


def parse_port(argv):
    """解析 --port N，返回 (端口, 错误信息)."""
    if "--port" not in argv:
        return DEFAULT_PORT, None
    index = argv.index("--port")
    if index + 1 >= len(argv):
        return DEFAULT_PORT, "--port 后面要跟端口号，例如 --port 52021"
    try:
        port = int(argv[index + 1])
    except ValueError:
        return DEFAULT_PORT, f"端口号无效：{argv[index + 1]}"
    if not 1 <= port <= 65535:
        return DEFAULT_PORT, f"端口号超出范围：{port}"
    return port, None


def split_target(text, default_port):
    """把 "192.168.1.5:52021" 拆成 (host, port)，没有端口就用默认值."""
    text = text.strip()
    if ":" in text:
        host, _, port_text = text.rpartition(":")
        if port_text.isdigit() and host:
            return host, int(port_text)
    return text, default_port


def run():
    port, error = parse_port(sys.argv[1:])
    if error:
        print(f"\n  {error}\n")
        return

    print("\n  wocli chat - 局域网聊天\n")
    print("  [1] 创建房间（你当服务端）")
    print("  [2] 加入房间（对方已创建）")
    print()
    try:
        choice = input("  选择 (1/2)：").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  已取消。\n")
        return

    conn = None
    if choice == "1":
        conn = run_server(port)
    elif choice == "2":
        print()
        try:
            target = input("  输入对方 IP（自定义端口写成 IP:端口）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  已取消。\n")
            return
        if not target:
            print("\n  没有输入 IP，已取消。\n")
            return
        host, target_port = split_target(target, port)
        conn = run_client(host, target_port)
    else:
        print("\n  无效选择。\n")
        return

    if conn is None:
        return

    running = [True]
    recv_thread = threading.Thread(
        target=receive_msg, args=(conn, running), daemon=True)
    recv_thread.start()

    chat_loop(conn, running)
    conn.close()
    print("\n  聊天结束。\n")
