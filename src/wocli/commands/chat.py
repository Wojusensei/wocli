"""wocli chat - 局域网终端聊天"""
import socket
import threading
import sys
import os
import platform


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "未知"


def receive_msg(sock, running):
    while running[0]:
        try:
            data = sock.recv(1024)
            if not data:
                break
            msg = data.decode("utf-8")
            if msg.strip() == "/quit":
                sys.stdout.write("\r\033[K  对方已退出聊天。\n")
                sys.stdout.flush()
                running[0] = False
                break
            sys.stdout.write(f"\r\033[K  [对方] {msg}\n  > ")
            sys.stdout.flush()
        except OSError:
            if running[0]:
                sys.stdout.write("\n  连接已断开。\n")
                sys.stdout.flush()
                running[0] = False
            break


def run_server(port):
    my_ip = get_local_ip()
    print(f"\n  你的 IP：{my_ip}")
    print(f"  等待对方连接...（请在运行我们的 wocli 之后把获取到的 IP 和端口 {port} 告诉你要建立聊天的对象。同样的，你也需要录入对方提供给你的 IP 和端口号）\n")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("0.0.0.0", port))
        server.listen(1)
        server.settimeout(60)
        conn, addr = server.accept()
        print(f"  对方已连接：{addr[0]}")
        print("  开始聊天，输入 /quit 退出。\n")
        return conn
    except socket.timeout:
        print("\n  等待超时，没人连接。\n")
        return None
    finally:
        server.close()


def run_client(host, port):
    print(f"\n  正在连接 {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        # 连接超时只用于 connect，聊天阶段改回阻塞式，
        # 否则 recv 会在 10 秒无消息后抛 timeout 误判为断开
        sock.settimeout(None)
        print(f"  已连接！")
        print("  开始聊天，输入 /quit 退出。\n")
        return sock
    except Exception as e:
        print(f"\n  连接失败：{e}\n")
        return None


def chat_loop(sock, running):
    try:
        while running[0]:
            msg = input("  > ")
            if msg.strip() == "/quit":
                sock.sendall(b"/quit")
                running[0] = False
                break
            sock.sendall(msg.encode("utf-8"))
    except (EOFError, KeyboardInterrupt):
        try:
            sock.sendall(b"/quit")
        except OSError:
            pass
        running[0] = False
    except OSError:
        print("\n  连接已断开。")
        running[0] = False


def run():
    port = 52020  # 固定端口

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
            host = input("  输入对方 IP：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  已取消。\n")
            return
        conn = run_client(host, port)
    else:
        print("\n  无效选择。\n")
        return

    if conn is None:
        return

    running = [True]
    recv_thread = threading.Thread(target=receive_msg, args=(conn, running), daemon=True)
    recv_thread.start()

    chat_loop(conn, running)
    conn.close()
    print("\n  聊天结束。\n")