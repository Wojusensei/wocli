"""gpa 校验、path 计数、cow 气泡、badapple 缓存自愈."""
import gzip
import os

from wocli.commands import badapple, cow, gpa, path_cmd


def _feed_inputs(monkeypatch, values):
    iterator = iter(values)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(iterator))


def _cancel_download(monkeypatch):
    def raise_eof(*args, **kwargs):
        raise EOFError
    monkeypatch.setattr("builtins.input", raise_eof)
    monkeypatch.delenv("WOCLI_BADAPPLE_FRAMES", raising=False)


def test_gpa_rejects_nan_credit(monkeypatch, capsys):
    _feed_inputs(monkeypatch, ["1", "nan", "95"])
    gpa.run()
    assert "正数" in capsys.readouterr().out


def test_gpa_rejects_out_of_range_grade(monkeypatch, capsys):
    _feed_inputs(monkeypatch, ["1", "3", "250"])
    gpa.run()
    assert "0~100" in capsys.readouterr().out


def test_gpa_normal(monkeypatch, capsys):
    _feed_inputs(monkeypatch, ["2", "3", "95", "2", "85"])
    gpa.run()
    out = capsys.readouterr().out
    assert "加权 GPA：3.88 / 4.0" in out   # (4.0*3 + 3.7*2) / 5


def test_cow_bubble_single_line():
    bubble = cow.make_bubble("哞")
    assert " < 哞 >" in bubble


def test_cow_bubble_wraps():
    bubble = cow.make_bubble(" ".join(["word"] * 20))
    assert bubble.count("\n") >= 4          # 上下边框 + 至少两行正文
    assert "<" not in bubble                # 多行时用 / \ | 边框


def test_path_counts_executables(tmp_path):
    exe = tmp_path / "tool"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    os.chmod(exe, 0o755)
    (tmp_path / "data.txt").write_text("x", encoding="utf-8")
    expected = 0 if os.name == "nt" else 1  # Windows 走扩展名判断
    assert path_cmd.count_executables(str(tmp_path)) == expected


def test_badapple_corrupt_cache_gets_deleted(tmp_path, monkeypatch, capsys):
    """上次下载中断留下的半截 gzip 不能让每次启动都崩：删掉重下."""
    cache = tmp_path / "badapple_frames.txt.gz"
    cache.write_bytes(b"not a gzip at all")
    monkeypatch.setattr(badapple, "_cache_path", lambda: str(cache))
    _cancel_download(monkeypatch)

    frames = badapple.load_frames(None)
    assert frames is None                   # 下载被取消，正常退出
    assert not cache.exists()               # 坏缓存已删
    assert "损坏" in capsys.readouterr().out


def test_badapple_partial_cache_gets_deleted(tmp_path, monkeypatch, capsys):
    """合法 gzip 但内容不完整（帧数过少）同样视为损坏."""
    cache = tmp_path / "badapple_frames.txt.gz"
    with gzip.open(str(cache), "wt", encoding="utf-8") as handle:
        handle.write("frame1\nSPLIT\nframe2")
    monkeypatch.setattr(badapple, "_cache_path", lambda: str(cache))
    _cancel_download(monkeypatch)

    badapple.load_frames(None)
    assert not cache.exists()
    assert "不完整" in capsys.readouterr().out


def test_badapple_warns_on_bad_path(tmp_path, monkeypatch, capsys):
    """显式传错路径要提示，不能静默换成默认帧源."""
    monkeypatch.setattr(badapple, "_cache_path",
                        lambda: str(tmp_path / "none.gz"))
    _cancel_download(monkeypatch)

    badapple.load_frames("/nonexistent/path")
    assert "找不到" in capsys.readouterr().out
