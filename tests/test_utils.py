"""utils 里的公共助手：外部命令的超时与解码容错、进度条渲染."""
import sys

from wocli.utils import format_bytes, render_bar, run_cmd


def test_run_cmd_missing_command():
    """命令不存在时返回 None，让调用方走回退分支而不是崩掉."""
    assert run_cmd(["definitely-not-a-real-command-wocli"]) is None


def test_run_cmd_output():
    assert run_cmd([sys.executable, "-c", "print('hello')"]) == "hello\n"


def test_run_cmd_timeout():
    """卡住的系统工具不能把整个命令拖死（macOS 的 system_profiler 就干过这事）."""
    assert run_cmd([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5) is None


def test_run_cmd_bad_decode():
    """输出不是本机编码时用替换字符兜住，别抛 UnicodeDecodeError."""
    code = "import sys; sys.stdout.buffer.write(b'\\xff\\xfe')"
    assert run_cmd([sys.executable, "-c", code]) is not None


def test_format_bytes():
    assert format_bytes(1536) == "1.5KB"


def test_render_bar_width():
    """进度条总宽度恒定，满格时不越界（update 覆盖重绘靠这个对齐）."""
    assert render_bar(0.5, 10) == "=====>    "
    assert render_bar(1.0, 10) == "=" * 10
