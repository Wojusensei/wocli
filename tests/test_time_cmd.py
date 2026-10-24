"""time / hash：失败要看得到 stderr、非 UTF-8 不能崩、哈希正确."""
import hashlib
import sys

from wocli.commands import hash_cmd, time_cmd


def _run_time(tmp_path, monkeypatch, capsys, code):
    script = tmp_path / "probe.py"
    script.write_text(code, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["time", str(script)])
    time_cmd.run()
    return capsys.readouterr().out


def test_time_shows_stderr_on_failure(tmp_path, monkeypatch, capsys):
    """跑失败的脚本时，报错原因在 stderr，不能吞掉."""
    code = "import sys\nsys.stderr.write('真实报错\\n')\nraise SystemExit(3)\n"
    out = _run_time(tmp_path, monkeypatch, capsys, code)
    assert "运行失败 (退出码 3)" in out
    assert "真实报错" in out


def test_time_survives_bad_utf8(tmp_path, monkeypatch, capsys):
    """子进程输出 GBK 之类的非 UTF-8 字节时不能抛 UnicodeDecodeError."""
    code = "import sys\nsys.stdout.buffer.write(b'\\xff\\xfe\\n')\n"
    out = _run_time(tmp_path, monkeypatch, capsys, code)
    assert "运行成功" in out


def test_time_success_shows_stdout(tmp_path, monkeypatch, capsys):
    out = _run_time(tmp_path, monkeypatch, capsys, "print('hello from child')\n")
    assert "hello from child" in out


def test_hash_known_content(tmp_path):
    target = tmp_path / "a.txt"
    target.write_bytes(b"wocli\n")
    md5, sha256 = hash_cmd.compute_hashes(str(target))
    assert md5 == hashlib.md5(b"wocli\n").hexdigest()
    assert sha256 == hashlib.sha256(b"wocli\n").hexdigest()


def test_hash_directory_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hash", str(tmp_path)])
    hash_cmd.run()
    assert "目录" in capsys.readouterr().out
