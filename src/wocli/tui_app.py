"""prompt_toolkit 交互层.

对外只暴露 ``run_app``；``wocli.tui`` 会在确认是 TTY 之后才导入本模块，
这样没装 prompt_toolkit 的环境仍然可以使用其它命令。
"""

import difflib
import os
import random
import shutil
import sys
import time
from typing import List, Optional

import prompt_toolkit
from prompt_toolkit import PromptSession
from prompt_toolkit.application import get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.shortcuts import CompleteStyle, clear, print_formatted_text
from prompt_toolkit.styles import DynamicStyle, Style

from wocli import __version__, terminal
from wocli.registry import ALIASES, COMMANDS
from wocli.status_data import StatusCollector
from wocli.tui_core import (
    AUTO_THEME,
    BOOT_QUIPS,
    DEFAULT_MODE,
    MODE_DESCRIPTIONS,
    MODES,
    SHELL_COMMANDS,
    THEMES,
    THEME_CHOICES,
    THEME_KEYS,
    build_banner_lines,
    build_boot_lines,
    build_doctor_lines,
    build_help_lines,
    build_panel_lines,
    build_status_segments,
    default_history_path,
    default_prefs_path,
    detect_theme_from_env,
    display_width,
    fit_segments,
    get_glyphs,
    get_theme,
    load_prefs,
    mode_label,
    next_mode,
    next_theme,
    normalize_mode,
    parse_shell_input,
    resolve_theme,
    save_prefs,
    status_lines,
)


# ---------- 状态与样式 ----------

class AppState:
    def __init__(self, theme_key: str, mode: str):
        self.theme_key = theme_key
        self.mode = mode
        self.hint = None
        self.said_goodbye = False
        self.start = time.monotonic()
        self._style_key = None
        self._style = None

    @property
    def theme(self):
        return get_theme(self.theme_key)

    def get_style(self) -> Style:
        if self._style is None or self._style_key != self.theme_key:
            self._style = build_style(self.theme)
            self._style_key = self.theme_key
        return self._style

    def set_theme(self, key: str) -> None:
        self.theme_key = key
        self.hint = None
        save_prefs(self.theme_key, self.mode)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.hint = None
        save_prefs(self.theme_key, self.mode)

    def cycle_mode(self) -> None:
        self.set_mode(next_mode(self.mode))


def build_style(theme) -> Style:
    return Style.from_dict({
        "prompt": "fg:%s bold" % theme.accent,
        "prompt.continuation": "fg:%s" % theme.muted,
        "bottom-toolbar": "bg:%s fg:%s noreverse" % (theme.bg, theme.sub),
        "bottom-toolbar.text": "bg:%s fg:%s noreverse" % (theme.bg, theme.sub),
        "status.model": "fg:%s bold" % theme.text,
        "status.seg": "fg:%s" % theme.sub,
        "status.muted": "fg:%s" % theme.muted,
        "status.branch": "fg:%s" % theme.blue,
        "status.clean": "fg:%s" % theme.green,
        "status.dirty": "fg:%s" % theme.yellow,
        "status.good": "fg:%s" % theme.green,
        "status.warn": "fg:%s" % theme.yellow,
        "status.bad": "fg:%s" % theme.red,
        "status.value": "fg:%s" % theme.text,
        "status.clock": "fg:%s" % theme.faint,
        "status.gap": "fg:%s" % theme.sub,
        "status.dead": "fg:%s" % theme.red,
        "status.fun0": "fg:%s" % theme.blue,
        "status.fun1": "fg:%s" % theme.purple,
        "status.fun2": "fg:%s" % theme.teal,
        "status.fun3": "fg:%s" % theme.yellow,
        "mode.arrow": "fg:%s bold" % theme.yellow,
        "mode.name": "fg:%s" % theme.yellow,
        "mode.hint": "fg:%s" % theme.muted,
        "panel.title": "fg:%s bold" % theme.text,
        "panel.ref": "fg:%s" % theme.blue,
        "panel.body": "fg:%s" % theme.sub,
        "panel.value": "fg:%s" % theme.text,
        "panel.muted": "fg:%s" % theme.muted,
        "panel.good": "fg:%s" % theme.green,
        "panel.warn": "fg:%s" % theme.yellow,
        "panel.bad": "fg:%s" % theme.red,
        "panel.slash": "fg:%s" % theme.faint,
        "panel.branch": "fg:%s" % theme.blue,
        "panel.italic": "fg:%s italic" % theme.sub,
        "waffle.app": "fg:%s" % theme.blue,
        "waffle.cache": "fg:%s" % theme.purple,
        "waffle.sys": "fg:%s" % theme.orange,
        "waffle.free": "fg:%s" % theme.faint,
        "waffle.other": "fg:%s" % theme.muted,
        "completion-menu.completion": "bg:%s fg:%s" % (theme.bg, theme.sub),
        "completion-menu.completion.current": "bg:%s fg:%s" % (
            theme.accent, theme.bg,
        ),
        "completion-menu.meta.completion": "bg:%s fg:%s" % (
            theme.bg, theme.muted,
        ),
        "completion-menu.meta.completion.current": "bg:%s fg:%s" % (
            theme.accent, theme.bg,
        ),
        "auto-suggest": "fg:%s" % theme.faint,
    })


# ---------- 补全 ----------

class WocliAutoSuggest(AutoSuggestFromHistory):
    """斜杠命令不要历史幽灵补全，否则输入 / 看起来像已经带了旧命令."""

    def get_suggestion(self, buffer, document):
        if document.text.startswith("/"):
            return None
        return super().get_suggestion(buffer, document)


class WocliCompleter(Completer):
    def __init__(self):
        self.commands = []
        seen = set()
        for name, description in SHELL_COMMANDS.items():
            self.commands.append((name, description))
            seen.add(name)
        for name, (_, description) in COMMANDS.items():
            if name == "tui" or name in seen:
                continue
            self.commands.append((name, description))
            seen.add(name)
        self.commands.sort(key=lambda item: item[0])

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.strip()
        if not stripped:
            return

        # /theme neon、/mode fun 这类参数补全
        if " " in stripped:
            parts = stripped.split()
            head = parts[0].lstrip("/").lower()
            current = "" if text.endswith(" ") else parts[-1]
            if head == "theme":
                options = [
                    (key, get_theme(key).label) for key in THEME_KEYS
                ]
                options.append((AUTO_THEME, "根据终端背景自动选择"))
            elif head == "mode":
                options = [(mode, mode_label(mode)) for mode in MODES]
            else:
                return
            for value, description in options:
                if value.startswith(current):
                    yield Completion(
                        value,
                        start_position=-len(current),
                        display=value,
                        display_meta=description,
                    )
            return

        # 第一段命令补全：/sta、sta 都能补出 status
        has_slash = stripped.startswith("/")
        name_prefix = stripped.lstrip("/").lower()
        for name, description in self.commands:
            if name.startswith(name_prefix):
                display = ("/" if has_slash else "") + name
                yield Completion(
                    display,
                    start_position=-len(stripped),
                    display=display,
                    display_meta=description,
                )


# ---------- 快捷键 ----------

def _create_key_bindings(state: AppState) -> KeyBindings:
    bindings = KeyBindings()
    last_ctrl_c = {"at": 0.0}

    @bindings.add("s-tab")
    def _cycle_mode(event):
        state.cycle_mode()
        event.app.invalidate()

    @bindings.add("c-k")
    def _command_palette(event):
        buffer = event.current_buffer
        if not buffer.text.startswith("/"):
            buffer.insert_text("/")
        buffer.start_completion(select_first=False)

    @bindings.add("c-l")
    def _clear_screen(event):
        event.app.renderer.clear()
        event.app.invalidate()

    @bindings.add("c-c")
    def _interrupt(event):
        buffer = event.current_buffer
        if buffer.text:
            buffer.reset()
            last_ctrl_c["at"] = 0.0
            event.app.invalidate()
            return
        now = time.monotonic()
        if now - last_ctrl_c["at"] <= 1.5:
            event.app.exit(exception=EOFError)
        else:
            last_ctrl_c["at"] = now
            state.hint = "再按一次 Ctrl-C 退出"
            event.app.invalidate()

    return bindings


# ---------- 输出 ----------

def terminal_width() -> int:
    return shutil.get_terminal_size((100, 30)).columns


def print_lines(lines, style: Style) -> None:
    for line in lines:
        if line:
            print_formatted_text(FormattedText(line), style=style)
        else:
            print_formatted_text("", style=style)


def prompt_symbol(state: AppState, glyphs):
    if state.mode == "整活":
        return str(glyphs["prompt_fun"]), "class:status.fun0"
    if state.mode == "死机":
        return str(glyphs["prompt_dead"]), "class:status.dead"
    return str(glyphs["prompt"]), "class:prompt"


def _append_bar_line(out, parts, width: int, background: str) -> None:
    """把一行状态铺满终端宽度，保证背景色是一条完整的横条."""
    used = 0
    for style, text in parts:
        used += display_width(text)
        style = (style + " " if style else "") + "bg:" + background
        out.append((style, text))
    pad = max(0, width - used)
    if pad:
        out.append(("bg:" + background, " " * pad))
    out.append(("bg:" + background, "\n"))


def hud_message(state: AppState, collector: StatusCollector, glyphs):
    """贴在输入框上方的 HUD：状态行 + 模式行 + 提示符.

    不用 PromptSession 的 bottom_toolbar：它固定在终端最底部，
    屏幕高的时候会和输入行之间空出一大段。这里把状态栏作为 prompt
    的一部分，输入到哪它就跟到哪。
    """
    width = terminal_width()
    snapshot = collector.snapshot()
    elapsed = time.monotonic() - state.start
    segments = build_status_segments(snapshot, elapsed, state.mode, glyphs)
    kept = fit_segments(segments, max(20, width - 1))

    hint = state.hint
    try:
        complete_state = get_app().current_buffer.complete_state
    except Exception:
        complete_state = None
    if complete_state is not None and complete_state.completions:
        updown = "↑↓" if glyphs.get("unicode") else "Up/Down"
        hint = "%s 浏览 · Tab 补全 · Esc 关闭" % updown

    line1, line2 = status_lines(
        kept, state.mode, hint, glyphs, width,
    )

    background = state.theme.bar_bg
    fragments = []
    _append_bar_line(fragments, line1, width, background)
    _append_bar_line(fragments, line2, width, background)
    symbol, style = prompt_symbol(state, glyphs)
    fragments.append((style, symbol + " "))
    return FormattedText(fragments)


def show_banner(state: AppState, snapshot, glyphs) -> None:
    print_lines(
        build_banner_lines(snapshot.version, state.theme, glyphs, terminal_width()),
        state.get_style(),
    )
    print_formatted_text("", style=state.get_style())


def play_boot(state: AppState, version: str, cores: int) -> None:
    lines = build_boot_lines(
        version, cores, state.theme, random.choice(BOOT_QUIPS),
    )
    for line in lines:
        print_formatted_text(FormattedText(line), style=state.get_style())
        time.sleep(0.08)
    time.sleep(0.12)


# ---------- 命令分发 ----------

def run_registry_command(command: str, args: List[str], state: AppState) -> None:
    old_argv = sys.argv
    sys.argv = [command] + list(args)
    try:
        COMMANDS[command][0]()
    except KeyboardInterrupt:
        print_formatted_text("", style=state.get_style())
        print_formatted_text(
            FormattedText([("class:panel.warn", "  (已中断)")]),
            style=state.get_style(),
        )
    except SystemExit:
        pass
    except BrokenPipeError:
        pass
    except Exception as exc:
        print_formatted_text(
            FormattedText([
                ("class:panel.bad", "  命令出错: %s: %s" % (
                    type(exc).__name__, exc,
                )),
            ]),
            style=state.get_style(),
        )
    finally:
        sys.argv = old_argv
        try:
            terminal.show_cursor()
        except Exception:
            pass
        print_formatted_text("", style=state.get_style())


def _print_theme_result(state: AppState, key: str) -> None:
    theme = get_theme(key)
    print_formatted_text(
        FormattedText([
            ("class:panel.muted", "  主题 -> "),
            ("class:panel.value", theme.label),
            ("class:panel.muted", "  (%s)" % theme.key),
        ]),
        style=state.get_style(),
    )


def _print_mode_result(state: AppState, mode: str) -> None:
    style = "class:panel.value"
    if mode == "整活":
        style = "class:status.fun0"
    elif mode == "死机":
        style = "class:panel.bad"
    print_formatted_text(
        FormattedText([
            ("class:panel.muted", "  模式 -> "),
            (style, mode_label(mode)),
            ("class:panel.muted", "  (shift+tab 也能切换)"),
        ]),
        style=state.get_style(),
    )
    description = MODE_DESCRIPTIONS.get(mode, "")
    if description:
        print_formatted_text(
            FormattedText([("class:panel.muted", "  " + description)]),
            style=state.get_style(),
        )


def handle_input(
    text: str,
    state: AppState,
    collector: StatusCollector,
    glyphs,
) -> Optional[str]:
    parsed = parse_shell_input(text)
    if parsed is None:
        print_formatted_text(
            FormattedText([
                ("class:panel.warn", "  无法解析这行输入（引号是否没闭合？）"),
            ]),
            style=state.get_style(),
        )
        return None

    command, args = parsed
    command = ALIASES.get(command, command)
    state.hint = None

    if command in ("quit", "exit", "q"):
        return "quit"

    if command == "goodbye":
        # 保留原命令的花式动画，播放完直接退出驾驶舱
        run_registry_command("goodbye", args, state)
        state.said_goodbye = True
        return "quit"

    if command in ("help", "?"):
        print_lines(build_help_lines(), state.get_style())
        return None

    if command in ("status", "context"):
        # 面板占大半屏，清屏后从顶部画，避免标题和 waffle 被顶出视口
        clear()
        symbol, symbol_style = prompt_symbol(state, glyphs)
        print_formatted_text(
            FormattedText([(symbol_style, symbol + " "), ("", text)]),
            style=state.get_style(),
        )
        print_lines(
            build_panel_lines(collector.snapshot(), glyphs, terminal_width()),
            state.get_style(),
        )
        return None

    if command == "theme":
        if args:
            key = args[0].lower()
            if key == AUTO_THEME:
                key = detect_theme_from_env()
            if key not in THEMES:
                print_formatted_text(
                    FormattedText([
                        ("class:panel.warn", "  未知主题，可选："),
                        ("class:panel.value", " / ".join(THEME_CHOICES)),
                    ]),
                    style=state.get_style(),
                )
                return None
            state.set_theme(key)
        else:
            state.set_theme(next_theme(state.theme_key))
        _print_theme_result(state, state.theme_key)
        return None

    if command == "mode":
        if args:
            mode = normalize_mode(args[0])
            if mode is None:
                print_formatted_text(
                    FormattedText([
                        ("class:panel.warn", "  未知模式，可选："),
                        ("class:panel.value", " / ".join(MODES)),
                    ]),
                    style=state.get_style(),
                )
                return None
            state.set_mode(mode)
        else:
            state.cycle_mode()
        _print_mode_result(state, state.mode)
        return None

    if command == "doctor":
        print_lines(
            build_doctor_lines(
                collector.snapshot(),
                state.mode,
                state.theme,
                prompt_toolkit.__version__,
                default_history_path(),
                default_prefs_path(),
            ),
            state.get_style(),
        )
        return None

    if command == "clear":
        clear()
        show_banner(state, collector.snapshot(), glyphs)
        return None

    if command == "version":
        print_formatted_text(
            FormattedText([
                ("class:panel.value", "  wocli v%s" % collector.snapshot().version),
            ]),
            style=state.get_style(),
        )
        return None

    if command == "tui":
        print_formatted_text(
            FormattedText([
                ("class:panel.muted", "  你已经驾驶舱里了，直接输入命令即可。"),
            ]),
            style=state.get_style(),
        )
        return None

    if command in COMMANDS:
        run_registry_command(command, args, state)
        return None

    suggestion = difflib.get_close_matches(
        command, sorted(set(SHELL_COMMANDS) | set(COMMANDS)), n=1, cutoff=0.55,
    )
    fragments = [
        ("class:panel.warn", "  未找到命令: %s" % command),
    ]
    if suggestion:
        fragments.append(("class:panel.muted", "  ·  你是不是想输入 "))
        fragments.append(("class:panel.ref", "/" + suggestion[0] + "？"))
    else:
        fragments.append(("class:panel.muted", "  ·  输入 /help 查看命令列表"))
    print_formatted_text(FormattedText(fragments), style=state.get_style())
    return None


# ---------- 主循环 ----------

def create_session(state: AppState, collector: StatusCollector, glyphs):
    try:
        history = FileHistory(default_history_path())
    except Exception:
        history = InMemoryHistory()

    # 多列菜单需要一点固定空间；短终端也不能一点不留，否则菜单会压在 HUD 上
    height = shutil.get_terminal_size((100, 30)).lines
    reserve = max(8, min(12, height - 22))

    session = PromptSession(
        message=lambda: hud_message(state, collector, glyphs),
        completer=WocliCompleter(),
        complete_while_typing=True,
        complete_style=CompleteStyle.MULTI_COLUMN,
        history=history,
        auto_suggest=WocliAutoSuggest(),
        style=DynamicStyle(state.get_style),
        key_bindings=_create_key_bindings(state),
        refresh_interval=1.0,
        reserve_space_for_menu=0,
        mouse_support=False,
        enable_open_in_editor=False,
        enable_system_prompt=False,
        erase_when_done=True,
    )

    def _sync_menu_space(buffer):
        # 只在补全菜单真正打开时借空间；否则 /status 面板会被白白顶出视口
        desired = reserve if buffer.complete_state else 0
        if session.reserve_space_for_menu != desired:
            session.reserve_space_for_menu = desired
            try:
                session.app.invalidate()
            except Exception:
                pass

    session.default_buffer.on_completions_changed += _sync_menu_space
    return session


def run_app(
    theme_key: Optional[str] = None,
    mode: Optional[str] = None,
    boot: bool = True,
    ascii_only: bool = False,
) -> None:
    prefs = load_prefs()
    theme_key = resolve_theme(theme_key, prefs.get("theme"))

    normalized = normalize_mode(mode) or prefs.get("mode") or DEFAULT_MODE
    if normalized not in MODES:
        normalized = DEFAULT_MODE

    state = AppState(theme_key, normalized)
    unicode_ok = bool(terminal.CAPS.get("unicode", True)) and not ascii_only
    glyphs = get_glyphs(unicode_ok)
    cwd = os.getcwd()

    clear()
    if boot:
        play_boot(state, __version__, os.cpu_count() or 0)

    collector = StatusCollector(cwd)
    collector.start()
    try:
        session = create_session(state, collector, glyphs)
        show_banner(state, collector.snapshot(), glyphs)
        while True:
            try:
                text = session.prompt()
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            if not text.strip():
                continue
            # erase_when_done 把光标留在输入行末尾，先换一行再回显命令
            print_formatted_text("", style=state.get_style())
            symbol, style = prompt_symbol(state, glyphs)
            print_formatted_text(
                FormattedText([(style, symbol + " "), ("", text)]),
                style=state.get_style(),
            )
            if handle_input(text, state, collector, glyphs) == "quit":
                break
    finally:
        collector.stop()
        save_prefs(state.theme_key, state.mode)

    if not state.said_goodbye:
        print_formatted_text(
            FormattedText([
                ("class:panel.muted", "\n  再会，记得喝水。"),
            ]),
            style=state.get_style(),
        )
