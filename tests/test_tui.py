"""驾驶舱入口、命令补全与状态对象的测试."""

import sys

import pytest

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from wocli import main, registry, tui
from wocli.tui_app import AppState, WocliCompleter, build_style, handle_input
from wocli.tui_core import GLYPHS_UNICODE, SHELL_COMMANDS, THEME_KEYS, get_theme


def test_registry_exposes_tui():
    assert "tui" in registry.COMMANDS
    assert "tui" in registry.HELP_GROUPS["效率"]
    assert registry.ALIASES["shell"] == "tui"
    assert registry.ALIASES["cockpit"] == "tui"


def test_main_reexports_registry():
    assert "tui" in main.COMMANDS
    assert main.HELP_GROUPS is registry.HELP_GROUPS


def test_parser_defaults():
    args = tui.build_parser().parse_args([])
    assert args.theme is None
    assert args.mode is None
    assert args.no_boot is False
    assert args.ascii is False


def test_parser_options():
    args = tui.build_parser().parse_args(
        ["--theme", "paper", "--mode", "fun", "--no-boot"]
    )
    assert args.theme == "paper"
    assert args.mode == "fun"
    assert args.no_boot is True
    assert tui.build_parser().parse_args(["--theme", "auto"]).theme == "auto"
    assert tui.build_parser().parse_args(["--ascii"]).ascii is True


def test_parser_rejects_unknown_theme():
    with pytest.raises(SystemExit):
        tui.build_parser().parse_args(["--theme", "nope"])


def test_no_args_launches_tui_on_tty(monkeypatch):
    called = []
    monkeypatch.setattr(main, "_should_launch_tui", lambda: True)
    monkeypatch.setitem(main.COMMANDS, "tui", (lambda: called.append(True), "test"))
    monkeypatch.setattr(main.sys, "argv", ["wocli"])
    main._dispatch()
    assert called == [True]


def test_no_args_prints_help_without_tty(monkeypatch, capsys):
    monkeypatch.setattr(main, "_should_launch_tui", lambda: False)
    monkeypatch.setattr(main.sys, "argv", ["wocli"])
    main._dispatch()
    assert "用法: wocli" in capsys.readouterr().out


def test_tui_options_forward_to_tui(monkeypatch):
    called = []
    monkeypatch.setitem(main.COMMANDS, "tui", (lambda: called.append(True), "test"))
    monkeypatch.setattr(main.sys, "argv", ["wocli", "--theme", "neon"])
    main._dispatch()
    assert called == [True]
    assert main.sys.argv == ["tui", "--theme", "neon"]


def test_should_launch_tui_respects_env(monkeypatch):
    class TTY:
        def isatty(self):
            return True

    monkeypatch.setattr(main.sys, "stdin", TTY())
    monkeypatch.setattr(main.sys, "stdout", TTY())
    monkeypatch.setenv("WOCLI_NO_TUI", "1")
    assert main._should_launch_tui() is False
    monkeypatch.delenv("WOCLI_NO_TUI")
    assert main._should_launch_tui() is True


def test_run_refuses_non_tty(monkeypatch, capsys):
    monkeypatch.setattr(tui, "is_interactive", lambda: False)
    monkeypatch.setattr(sys, "argv", ["wocli", "tui"])
    tui.run()
    output = capsys.readouterr().out
    assert "需要交互式终端" in output
    assert "wocli sys" in output


def test_completer_suggests_commands():
    completer = WocliCompleter()
    completions = list(completer.get_completions(Document("/sta"), CompleteEvent()))
    assert any(completion.text == "/status" for completion in completions)


def test_completer_suggests_theme_values():
    completer = WocliCompleter()
    completions = list(completer.get_completions(
        Document("/theme n"), CompleteEvent(),
    ))
    assert any(completion.text == "neon" for completion in completions)
    completions = list(completer.get_completions(
        Document("/theme p"), CompleteEvent(),
    ))
    assert any(completion.text == "paper" for completion in completions)
    completions = list(completer.get_completions(
        Document("/theme a"), CompleteEvent(),
    ))
    assert any(completion.text == "auto" for completion in completions)


def test_completer_suggests_mode_values():
    completer = WocliCompleter()
    completions = list(completer.get_completions(
        Document("/mode 整"), CompleteEvent(),
    ))
    assert any(completion.text == "整活" for completion in completions)


def test_build_style_resolves_status_class():
    for key in THEME_KEYS:
        style = build_style(get_theme(key))
        attrs = style.get_attrs_for_style_str("class:status.model")
        assert attrs.color is not None


def test_goodbye_exits_cockpit(monkeypatch):
    import wocli.tui_app as tui_app

    calls = []
    monkeypatch.setattr(
        tui_app, "run_registry_command",
        lambda command, args, state: calls.append(command),
    )
    monkeypatch.setattr(tui_app, "save_prefs", lambda *args, **kwargs: None)
    state = AppState("catppuccin", "正常")

    assert "goodbye" in SHELL_COMMANDS
    assert handle_input("/goodbye", state, None, GLYPHS_UNICODE) == "quit"
    assert calls == ["goodbye"]
    assert state.said_goodbye is True


def test_app_state_cycles_without_writing_prefs(monkeypatch):
    import wocli.tui_app as tui_app

    monkeypatch.setattr(tui_app, "save_prefs", lambda *args, **kwargs: None)
    state = AppState("catppuccin", "正常")
    assert state.theme.key == "catppuccin"
    state.cycle_mode()
    assert state.mode == "整活"
    state.set_theme("amber")
    assert state.theme.key == "amber"
    assert state.get_style() is state.get_style()


def test_app_state_unknown_theme_falls_back(monkeypatch):
    import wocli.tui_app as tui_app

    monkeypatch.setattr(tui_app, "save_prefs", lambda *args, **kwargs: None)
    state = AppState("nope", "正常")
    assert state.theme.key == "catppuccin"
