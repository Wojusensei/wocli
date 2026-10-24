"""regex：限时匹配，灾难性回溯不能把命令卡死."""
from wocli.commands import regex_cmd


def test_normal_matches():
    matches, truncated, error = regex_cmd.find_matches(r"\d+", "a1 b22 c333")
    assert error is None
    assert truncated is False
    assert matches == [[1, 2, "1"], [4, 6, "22"], [8, 11, "333"]]


def test_no_match():
    assert regex_cmd.find_matches(r"xyz", "abc") == ([], False, None)


def test_timeout_is_killed(monkeypatch):
    """(a+)+$ 遇长输入会灾难性回溯：旧实现会卡几分钟只能杀进程.

    匹配放在子进程里限时跑（n=26 实测要 2.4 秒以上，这里限时 1 秒），
    超时杀掉并给出提示。线程方案不可行：正则引擎在 C 层不吐 GIL，
    主线程的限时等待会被硬拖到匹配结束。
    """
    monkeypatch.setattr(regex_cmd, "MATCH_TIMEOUT_SECONDS", 1)
    matches, truncated, error = regex_cmd.find_matches(r"(a+)+$", "a" * 26 + "!")
    assert error == "timeout"
    assert matches == []


def test_child_error_is_reported():
    """传给 find_matches 的表达式直接在子进程里编译失败时，要能报出来."""
    matches, truncated, error = regex_cmd.find_matches("(", "abc")
    assert matches == []
    assert error
    assert "unterminated subpattern" in error


def test_truncation_flag():
    """匹配数超过上限时带 truncated 标记."""
    matches, truncated, error = regex_cmd.find_matches("a", "a" * 10)
    assert error is None
    assert len(matches) == 10
    assert truncated is False
