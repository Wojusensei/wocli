"""chat：握手、杂连接不能顶掉房间、客户端要会重试."""
import socket
import threading
import time

import pytest

from wocli.commands import chat


def test_split_target():
    assert chat.split_target("192.168.1.5", 52020) == ("192.168.1.5", 52020)
    assert chat.split_target("192.168.1.5:52021", 52020) == (
        "192.168.1.5", 52021)
    # 冒号后面不是端口就整串当主机名
    assert chat.split_target("host:abc", 52020) == ("host:abc", 52020)


def test_parse_port():
    assert chat.parse_port([]) == (chat.DEFAULT_PORT, None)
    assert chat.parse_port(["--port", "52021"]) == (52021, None)
    assert chat.parse_port(["--port"])[1] is not None
    assert chat.parse_port(["--port", "abc"])[1] is not None
    assert chat.parse_port(["--port", "70000"])[1] is not None


@pytest.mark.parametrize("exc,expect", [
    (ConnectionRefusedError(61, "refused"), "端口没有在监听"),
    (socket.timeout(), "超时"),
    (OSError(65, "no route"), "网络不可达"),
])
def test_describe_error(exc, expect):
    assert expect in chat.describe_error(exc)


def test_handshake_roundtrip():
    """握手成功后，后面的聊天内容不能被握手读串."""
    left, right = socket.socketpair()
    result = {}

    def server_side():
        result["ok"] = chat.handshake_recv(right)
        result["line"] = chat.read_line(right)

    thread = threading.Thread(target=server_side)
    thread.start()
    try:
        left.settimeout(5)
        assert chat.handshake_send(left) is True
        left.sendall("你好\n".encode("utf-8"))
        thread.join(5)
        assert result["ok"] is True
        assert result["line"] == "你好".encode("utf-8")
    finally:
        left.close()
        right.close()


def _listening_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    return server, server.getsockname()[1]


def test_bad_peer_does_not_take_the_room():
    """杂连接（端口扫描、旧版本、误连）不能顶掉房间.

    旧实现只 accept 一次，任何一个杂连接都会让后面真正的人收到 connection refused。
    """
    server, port = _listening_server()
    accepted = {}

    def serve():
        accepted["conn"] = chat.wait_for_peer(server, wait_seconds=10)

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        junk = socket.create_connection(("127.0.0.1", port), timeout=5)
        junk.settimeout(5)
        junk.sendall(b"GET / HTTP/1.0\r\n\r\n")   # 不说暗号
        junk.recv(64)
        junk.close()
        time.sleep(0.3)

        conn, error = chat.connect_to_peer("127.0.0.1", port, retry_seconds=5)
        assert error is None
        assert conn is not None
        thread.join(5)
        assert accepted["conn"] is not None

        conn.sendall("hello\n".encode("utf-8"))
        assert chat.read_line(accepted["conn"]) == b"hello"
        conn.close()
    finally:
        server.close()


def test_client_retries_until_room_is_ready():
    """客户端比房间早启动几秒也要能连上（旧实现只试一次就报失败）."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    result = {}

    def connect():
        result["conn"], result["error"] = chat.connect_to_peer(
            "127.0.0.1", port, retry_seconds=8)

    client_thread = threading.Thread(target=connect)
    client_thread.start()
    time.sleep(1.5)

    late_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    late_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    late_server.bind(("127.0.0.1", port))
    late_server.listen(4)
    accepted = {}

    def serve():
        accepted["conn"] = chat.wait_for_peer(late_server, wait_seconds=8)

    server_thread = threading.Thread(target=serve)
    server_thread.start()
    client_thread.join(10)
    server_thread.join(10)
    try:
        assert result.get("error") is None
        assert result.get("conn") is not None
        assert accepted.get("conn") is not None
    finally:
        for sock in (result.get("conn"), accepted.get("conn"), late_server):
            if sock is not None:
                sock.close()


def test_local_ip_candidates_filters_unusable():
    """列出来的 IP 里不能有回环/链路本地地址（对方连不上那种）."""
    for ip in chat.local_ip_candidates():
        assert not ip.startswith("127.")
        assert not ip.startswith("169.254.")
