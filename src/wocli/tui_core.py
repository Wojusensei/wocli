"""驾驶舱 TUI 的纯渲染核心.

这里刻意不 import prompt_toolkit：面板、状态栏、waffle 都只是
[(style, text)] 片段，既能单测，也方便以后换渲染后端。
"""

import datetime
import json
import os
import random
import shlex
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from wocli import terminal
from wocli.registry import COMMANDS, HELP_GROUPS
from wocli.status_data import StatusSnapshot

Fragment = Tuple[str, str]
Line = List[Fragment]


# ---------- 图元 ----------

GLYPHS_UNICODE = {
    "unicode": True,
    "waffle": "▦",
    "free": "▦",
    "prompt": "❯",
    "prompt_fun": "✦",
    "prompt_dead": "▓",
    "folder": "▪",
    "branch": "◈",
    "elbow": "└",
    "check": "✓",
    "dirty": "●",
    "clock": "◷",
    "arrows": "▶▶",
    "rule": "─",
    "spark": "✦",
    "minus": "−",
    "ellipsis": "…",
    "arrow": "→",
    "times": "×",
    "glitch": "▓▒░█",
    "battery_full": "◕",
    "battery_mid": "◑",
    "battery_low": "◔",
    "battery_empty": "○",
}

GLYPHS_ASCII = {
    "unicode": False,
    "waffle": "#",
    "free": ".",
    "prompt": ">",
    "prompt_fun": "*",
    "prompt_dead": "#",
    "folder": "dir",
    "branch": "git",
    "elbow": "\\-",
    "check": "ok",
    "dirty": "*",
    "clock": "t",
    "arrows": ">>",
    "rule": "-",
    "spark": "*",
    "minus": "-",
    "ellipsis": "...",
    "arrow": "->",
    "times": "x",
    "glitch": "#%*@",
    "battery_full": "B",
    "battery_mid": "b",
    "battery_low": "!",
    "battery_empty": "?",
}


def get_glyphs(unicode_ok: bool = True) -> Dict[str, object]:
    return GLYPHS_UNICODE if unicode_ok else GLYPHS_ASCII


def display_width(text: str) -> int:
    """终端显示宽度：中文/全角占两列，组合字符不占列."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def pad_display(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def shorten(text: str, limit: int, ellipsis: str = "…") -> str:
    if display_width(text) <= limit:
        return text
    ellipsis_width = display_width(ellipsis)
    if limit <= ellipsis_width:
        return ellipsis[:limit]
    out = ""
    for char in text:
        if display_width(out + char) > limit - ellipsis_width:
            break
        out += char
    return out + ellipsis


def human_bytes(value: int) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "?"
    if size < 1024:
        return "%d B" % int(size)
    for unit in ("KB", "MB", "GB", "TB"):
        size /= 1024.0
        if size < 1024 or unit == "TB":
            return "%.1f %s" % (size, unit)
    return "%.1f PB" % size


def percent(part: int, total: int) -> float:
    if not total:
        return 0.0
    return max(0.0, min(100.0, 100.0 * part / total))


def allocate_cells(values: Sequence[float], cells: int = 100) -> List[int]:
    """最大余数法把内存分类映射到固定格数，保证总和恒等于 cells."""
    values = [max(0.0, float(value)) for value in values]
    total = sum(values)
    if total <= 0:
        return [0] * len(values)

    raw = [value / total * cells for value in values]
    counts = [int(value) for value in raw]
    remainder = cells - sum(counts)
    order = sorted(
        range(len(values)), key=lambda index: raw[index] - counts[index], reverse=True
    )
    for index in order[:remainder]:
        counts[index] += 1
    return [max(0, count) for count in counts]


def format_elapsed(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%ds" % seconds
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return "%dm%02ds" % (minutes, sec)
    hours, minutes = divmod(minutes, 60)
    return "%dh%02dm" % (hours, minutes)


def signal_bars(rssi: Optional[int], unicode_ok: bool = True) -> Tuple[str, str]:
    if rssi is None:
        return "", "离线"
    if rssi > -50:
        bars, label = "▂▄▆█", "极强"
    elif rssi > -60:
        bars, label = "▂▄▆", "强"
    elif rssi > -70:
        bars, label = "▂▄", "中"
    elif rssi > -80:
        bars, label = "▂", "弱"
    else:
        bars, label = "▁", "差"
    if not unicode_ok:
        bars = {
            "极强": "||||",
            "强": "|||",
            "中": "||",
            "弱": "|",
            "差": ".",
        }[label]
    return bars, label


def battery_glyph(value: int, unicode_ok: bool = True) -> str:
    if not unicode_ok:
        return "[b]"
    if value >= 75:
        return "◕"
    if value >= 40:
        return "◑"
    if value >= 15:
        return "◔"
    return "○"


def glitch(text: str, seed: int, unicode_ok: bool = True) -> str:
    """死机模式的假故障：只替换少量字符，不能把宽度和可读性搞崩."""
    rng = random.Random(seed)
    alphabet = "▓▒░█" if unicode_ok else "#%*@"
    chars = []
    for char in text:
        if char != " " and rng.random() < 0.07:
            chars.append(rng.choice(alphabet))
        else:
            chars.append(char)
    return "".join(chars)


# ---------- 主题 ----------

@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    bg: str
    bar_bg: str
    text: str
    sub: str
    muted: str
    faint: str
    blue: str
    purple: str
    green: str
    yellow: str
    orange: str
    red: str
    teal: str
    accent: str


THEMES = {
    "catppuccin": Theme(
        key="catppuccin",
        label="Catppuccin Mocha",
        bg="#1e1e2e",
        bar_bg="#252537",
        text="#cdd6f4",
        sub="#a6adc8",
        muted="#7f849c",
        faint="#585b70",
        blue="#89b4fa",
        purple="#cba6f7",
        green="#a6e3a1",
        yellow="#f9e2af",
        orange="#fab387",
        red="#f38ba8",
        teal="#94e2d5",
        accent="#89b4fa",
    ),
    "neon": Theme(
        key="neon",
        label="赛博霓虹",
        bg="#07070f",
        bar_bg="#12121f",
        text="#e8f6ff",
        sub="#9ad8e6",
        muted="#5f8a99",
        faint="#33515c",
        blue="#00e5ff",
        purple="#ff2bd6",
        green="#39ff9e",
        yellow="#f7ff6b",
        orange="#ff9f1c",
        red="#ff4d6d",
        teal="#00ffd5",
        accent="#ff2bd6",
    ),
    "amber": Theme(
        key="amber",
        label="琥珀 CRT",
        bg="#120d06",
        bar_bg="#1f170b",
        text="#ffe3b3",
        sub="#d9b072",
        muted="#9a7742",
        faint="#5c4826",
        blue="#ffb347",
        purple="#ff8c42",
        green="#b5e48c",
        yellow="#ffe066",
        orange="#ffa94d",
        red="#ff6b6b",
        teal="#ffd8a8",
        accent="#ffb347",
    ),
    "paper": Theme(
        key="paper",
        label="纸白 Paper",
        bg="#f5f2ea",
        bar_bg="#e7e1d4",
        text="#2b2b2b",
        sub="#5a5a5a",
        muted="#7a7468",
        faint="#b0a89a",
        blue="#2f6fa5",
        purple="#7b4fa8",
        green="#3d7a4e",
        yellow="#9a6b00",
        orange="#b35c00",
        red="#b23b3b",
        teal="#1f7a7a",
        accent="#2f6fa5",
    ),
}

THEME_KEYS = tuple(THEMES)
DEFAULT_THEME = "catppuccin"
AUTO_THEME = "auto"
THEME_CHOICES = THEME_KEYS + (AUTO_THEME,)


def get_theme(key: Optional[str]) -> Theme:
    return THEMES.get(key or "", THEMES[DEFAULT_THEME])


def next_theme(key: Optional[str]) -> str:
    keys = list(THEME_KEYS)
    try:
        index = keys.index(key or "")
    except ValueError:
        return keys[0]
    return keys[(index + 1) % len(keys)]


def detect_theme_from_env(environ=None) -> str:
    """根据终端背景色猜一个能看清的主题.

    COLORFGBG 是最常见的约定（fg;bg，例如 15;0 是亮字暗底，0;15 是暗字亮底）。
    没有这个变量、也没有 TERM_BACKGROUND 时，默认沿用 Catppuccin。
    """
    env = environ if environ is not None else os.environ

    background = str(env.get("TERM_BACKGROUND", "")).strip().lower()
    if background == "light":
        return "paper"
    if background == "dark":
        return DEFAULT_THEME

    colorfgbg = str(env.get("COLORFGBG", "")).strip()
    if not colorfgbg:
        return DEFAULT_THEME
    parts = [part.strip() for part in colorfgbg.split(";") if part.strip()]
    if not parts or not parts[-1].isdigit():
        return DEFAULT_THEME
    index = int(parts[-1])
    if index in (7, 15, 231) or index >= 248:
        return "paper"
    return DEFAULT_THEME


def resolve_theme(
    requested: Optional[str] = None,
    saved: Optional[str] = None,
    environ=None,
) -> str:
    for candidate in (requested, saved):
        if candidate == AUTO_THEME:
            return detect_theme_from_env(environ)
        if candidate in THEMES:
            return candidate
    return detect_theme_from_env(environ)


# ---------- 人格模式 ----------

MODES = ("正常", "整活", "死机")
MODE_ALIASES = {
    "normal": "正常",
    "fun": "整活",
    "chaos": "整活",
    "dead": "死机",
}
DEFAULT_MODE = "正常"


def normalize_mode(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if value in MODES:
        return value
    return MODE_ALIASES.get(value.lower())


def next_mode(mode: str) -> str:
    try:
        index = MODES.index(mode)
    except ValueError:
        return MODES[0]
    return MODES[(index + 1) % len(MODES)]


def mode_label(mode: str) -> str:
    return mode + "模式"


MODE_DESCRIPTIONS = {
    "正常": "标准配色 · 稳定提示符，适合日常使用",
    "整活": "✦ 提示符 · 轮换强调色 · 每日运势，视觉更活跃",
    "死机": "红色故障风 · 随机乱码，纯整活",
}


FORTUNES = ("大吉", "吉", "小吉", "末吉", "凶", "大凶")


def fortune_for_today(day: Optional[datetime.date] = None) -> str:
    day = day or datetime.date.today()
    return FORTUNES[day.toordinal() % len(FORTUNES)]


# ---------- 状态栏 ----------

@dataclass(frozen=True)
class StatusSegment:
    key: str
    parts: Tuple[Fragment, ...]
    priority: int = 1

    @property
    def text(self) -> str:
        return "".join(text for _, text in self.parts)


def _dead_style(style: str, dead: bool) -> str:
    if dead and style.startswith("status."):
        return "class:status.dead"
    return "class:" + style


def build_status_segments(
    snapshot: StatusSnapshot,
    elapsed_seconds: float,
    mode: str,
    glyphs: Dict[str, object],
    now: Optional[float] = None,
) -> List[StatusSegment]:
    """把快照拆成语义分段；每段带优先级，窄终端按优先级丢段."""
    import time as _time

    now = now if now is not None else _time.time()
    dead = mode == "死机"
    fun = mode == "整活"
    unicode_ok = bool(glyphs.get("unicode", True))

    def style(name: str) -> str:
        return _dead_style(name, dead)

    segments = []

    version_text = "wocli v%s" % snapshot.version
    if dead:
        version_text = glitch(version_text, int(now) // 2, unicode_ok)
    version_parts = []
    if fun:
        version_parts.append(
            ("class:status.fun%d" % (int(now) // 2 % 4), str(glyphs["spark"]) + " ")
        )
    version_parts.append((style("status.model"), version_text))
    segments.append(StatusSegment("version", tuple(version_parts), 0))

    cwd = os.path.normpath(snapshot.cwd)
    home = os.path.normpath(os.path.expanduser("~"))
    cwd_name = "~" if cwd == home else (os.path.basename(cwd) or cwd)
    if dead:
        cwd_name = glitch(cwd_name, int(now) // 2 + 1, unicode_ok)
    segments.append(StatusSegment(
        "cwd",
        (
            (style("status.muted"), str(glyphs["folder"]) + " "),
            (style("status.seg"), cwd_name),
        ),
        0,
    ))

    if snapshot.git is not None:
        branch = shorten(
            snapshot.git.branch, 26, str(glyphs.get("ellipsis", "…"))
        )
        if dead:
            branch = glitch(branch, int(now) // 2 + 2, unicode_ok)
        check_style = "status.clean" if not snapshot.git.dirty else "status.dirty"
        check = glyphs["check"] if not snapshot.git.dirty else glyphs["dirty"]
        segments.append(StatusSegment(
            "git",
            (
                (style("status.muted"), str(glyphs["branch"]) + " "),
                (style("status.branch"), branch),
                (style(check_style), " " + str(check)),
            ),
            0,
        ))

    if snapshot.battery is not None:
        value = snapshot.battery.percent
        tone = (
            "status.good"
            if value >= 50
            else "status.warn" if value >= 20 else "status.bad"
        )
        segments.append(StatusSegment(
            "battery",
            (
                (style(tone), battery_glyph(value, unicode_ok)),
                (style("status.value"), " %d%%" % value),
            ),
            1,
        ))

    if snapshot.wifi is not None and snapshot.wifi.rssi is not None:
        bars, label = signal_bars(snapshot.wifi.rssi, unicode_ok)
        tone = (
            "status.good"
            if label in ("极强", "强")
            else "status.warn" if label == "中" else "status.bad"
        )
        segments.append(StatusSegment(
            "wifi",
            (
                (style(tone), bars),
                (style("status.seg"), " " + label),
            ),
            1,
        ))

    if snapshot.cpu is not None and snapshot.cpu.percent is not None:
        value = snapshot.cpu.percent
        tone = "status.bad" if value >= 85 else "status.warn" if value >= 60 else "status.seg"
        segments.append(StatusSegment(
            "cpu", ((style(tone), "CPU %d%%" % int(round(value))),), 2
        ))

    segments.append(StatusSegment(
        "elapsed",
        (
            (style("status.muted"), str(glyphs["clock"]) + " "),
            (style("status.seg"), format_elapsed(elapsed_seconds)),
        ),
        2,
    ))

    if snapshot.git is not None and (
        snapshot.git.additions or snapshot.git.deletions
    ):
        segments.append(StatusSegment(
            "diff",
            (
                (style("status.good"), "+%d" % snapshot.git.additions),
                (style("status.seg"), " "),
                (style("status.bad"), "%s%d" % (
                    glyphs.get("minus", "−"), snapshot.git.deletions,
                )),
            ),
            2,
        ))

    if fun:
        segments.append(StatusSegment(
            "fortune",
            ((
                "class:status.fun%d" % (int(now) // 2 % 4),
                "%s %s" % (glyphs["spark"], fortune_for_today()),
            ),),
            3,
        ))

    segments.append(StatusSegment(
        "clock",
        ((style("status.clock"), _time.strftime("%Y-%m-%d %H:%M", _time.localtime(now))),),
        3,
    ))

    return segments


def fit_segments(
    segments: Sequence[StatusSegment], width: int, gap: int = 2
) -> List[StatusSegment]:
    """按优先级往状态栏里塞段；塞不下的直接省略，保证不换行、不截断中文."""
    if not segments:
        return []

    kept = set()
    used = 0
    for priority in sorted({segment.priority for segment in segments}):
        for index, segment in enumerate(segments):
            if index in kept or segment.priority != priority:
                continue
            extra = display_width(segment.text) + (gap if kept else 0)
            if used + extra <= width:
                kept.add(index)
                used += extra

    if not kept:
        kept.add(0)
    return [segments[index] for index in sorted(kept)]


def status_lines(
    segments: Sequence[StatusSegment],
    mode: str,
    hint: Optional[str] = None,
    glyphs: Optional[Dict[str, object]] = None,
    width: Optional[int] = None,
    now: Optional[float] = None,
) -> Tuple[List[Fragment], List[Fragment]]:
    """返回状态行和模式行，方便调用方给两行分别铺背景色."""
    import time as _time

    glyphs = glyphs or GLYPHS_UNICODE
    now = now if now is not None else _time.time()

    line1 = []
    inline = [segment for segment in segments if segment.key != "clock"]
    clock = next((segment for segment in segments if segment.key == "clock"), None)

    for index, segment in enumerate(inline):
        if index:
            line1.append(("class:status.gap", "  "))
        line1.extend(segment.parts)

    if clock is not None:
        used = sum(display_width(segment.text) for segment in inline)
        used += 2 * max(0, len(inline) - 1)
        pad = max(2, (width or 0) - used - display_width(clock.text))
        line1.append(("class:status.gap", " " * pad))
        line1.extend(clock.parts)

    mode_style = "class:mode.name"
    if mode == "整活":
        mode_style = "class:status.fun%d" % (int(now) // 2 % 4)
    elif mode == "死机":
        mode_style = "class:status.dead"

    line2 = [
        ("class:mode.arrow", str(glyphs["arrows"]) + " "),
        (mode_style, mode_label(mode) + " on"),
        ("class:mode.hint", "  (shift+tab 切换)"),
    ]
    if hint:
        line2.append(("class:status.warn", "  ·  " + hint))
    return line1, line2


def status_fragments(
    segments: Sequence[StatusSegment],
    mode: str,
    hint: Optional[str] = None,
    glyphs: Optional[Dict[str, object]] = None,
    width: Optional[int] = None,
    now: Optional[float] = None,
) -> List[Fragment]:
    """两行状态拼成一段 FormattedText（中间用换行分隔）."""
    line1, line2 = status_lines(segments, mode, hint, glyphs, width, now)
    return line1 + [("", "\n")] + line2


# ---------- 欢迎界面 / 启动自检 ----------

def _center(parts: Line, width: int) -> Line:
    total = sum(display_width(text) for _, text in parts)
    pad = max(0, (width - total) // 2) if width else 0
    return [("", " " * pad)] + list(parts)


def build_banner_lines(
    version: str,
    theme: Theme,
    glyphs: Dict[str, object],
    width: int,
) -> List[Line]:
    width = width or 80
    unicode_ok = bool(glyphs.get("unicode", True))
    logo_source = terminal.LOGO_UNICODE if unicode_ok else terminal.LOGO_ASCII
    longest = max((display_width(line) for _, line in logo_source), default=0)
    if longest > max(10, width - 2):
        logo_source = terminal.LOGO_ASCII
        longest = max((display_width(line) for _, line in logo_source), default=0)
    if longest > max(10, width - 2):
        logo_source = []

    gradient = [
        theme.blue,
        theme.purple,
        theme.accent,
        theme.orange,
        theme.yellow,
        theme.green,
    ]
    lines = []
    for index, (_, line) in enumerate(logo_source):
        color = gradient[index % len(gradient)]
        lines.append(_center([("fg:%s bold" % color, line)], width))

    lines.append(_center(
        [
            ("fg:%s bold" % theme.text, "wocli v%s" % version),
            ("fg:%s" % theme.muted, "  ·  cockpit"),
        ],
        width,
    ))
    lines.append(_center(
        [("fg:%s" % theme.sub, "一个为发电而生的终端驾驶舱")],
        width,
    ))
    rule = str(glyphs["rule"]) * max(8, min(width - 2, 62))
    lines.append(_center([("fg:%s" % theme.faint, rule)], width))
    lines.append(_center(
        [
            ("fg:%s" % theme.accent, "/status"),
            ("fg:%s" % theme.muted, " 看系统上下文   "),
            ("fg:%s" % theme.accent, "/help"),
            ("fg:%s" % theme.muted, " 命令列表   "),
            ("fg:%s" % theme.accent, "Ctrl+K"),
            ("fg:%s" % theme.muted, " 命令面板"),
        ],
        width,
    ))
    lines.append(_center(
        [
            ("fg:%s" % theme.accent, "Shift+Tab"),
            ("fg:%s" % theme.muted, " 切换人格模式   "),
            ("fg:%s" % theme.accent, "Ctrl+C %s2" % glyphs.get("times", "×")),
            ("fg:%s" % theme.muted, " 退出"),
        ],
        width,
    ))
    return lines


BOOT_QUIPS = (
    "未检测到正在运行的 bug（这不科学）",
    "今日运势已注入，失败率下降 3%",
    "室友的 WiFi 已列入观察名单",
    "发电模块预热完成，可以开始整活",
)


def build_boot_lines(
    version: str,
    cores: int,
    theme: Theme,
    quip: Optional[str] = None,
) -> List[Line]:
    quip = quip or BOOT_QUIPS[0]
    muted = "fg:%s" % theme.muted
    ok = "fg:%s" % theme.green
    warn = "fg:%s" % theme.yellow
    return [
        [
            (muted, "WOCLI BIOS v%s " % version),
            (muted, "." * 26 + " "),
            (ok, "OK"),
        ],
        [
            (muted, "CPU %d 核 · 内存自检 " % cores),
            (muted, "." * 16 + " "),
            (ok, "OK"),
        ],
        [
            (muted, "装载发电模块 "),
            (muted, "." * 25 + " "),
            (ok, "OK"),
        ],
        [
            (warn, "[  OK  ] "),
            (muted, quip),
        ],
    ]


# ---------- 系统面板 ----------

def _display_note(note: str, glyphs: Dict[str, object]) -> str:
    """WiFi 提示里带 →，纯 ASCII 终端要换成 ->."""
    return (note or "").replace("→", str(glyphs.get("arrow", "→")))


def _section(title: str, ref: str, body: Line, glyphs: Dict[str, object]) -> List[Line]:
    return [
        [
            ("class:panel.title", title),
            ("class:panel.slash", " · "),
            ("class:panel.ref", ref),
        ],
        [("class:panel.slash", str(glyphs["elbow"]) + " ")] + list(body),
    ]


def system_label(system) -> str:
    """系统名优先用 read_system 生成的友好标签（macOS 26 / Windows 11 / Ubuntu）。"""
    return system.os_label or ("%s %s" % (
        system.os_name, system.os_release,
    )).strip()


def _memory_block(snapshot: StatusSnapshot, glyphs: Dict[str, object], width: int) -> List[Line]:
    memory = snapshot.memory
    if memory is None or not memory.categories:
        return [[("class:panel.muted", "内存分类数据未获取到")]]

    cats = list(memory.categories)
    counts = allocate_cells([category.bytes for category in cats], 100)
    flat = []
    for category, count in zip(cats, counts):
        flat.extend([category] * count)
    if len(flat) < 100:
        flat.extend([None] * (100 - len(flat)))

    glyph = str(glyphs["waffle"])
    free_glyph = str(glyphs["free"])
    waffle_lines = []
    for row in range(10):
        line = []
        for col in range(10):
            index = row * 10 + col
            category = flat[index] if index < len(flat) else None
            if category is None:
                line.append(("class:waffle.free", free_glyph))
            else:
                line.append(("class:waffle." + category.key, glyph))
            if col < 9:
                line.append(("", " "))
        waffle_lines.append(line)

    legend_lines = [
        [("class:panel.title", "wocli v%s" % snapshot.version)],
        [("class:panel.body", "%s · %s" % (
            system_label(snapshot.system),
            snapshot.system.machine,
        ))],
        [("class:panel.body", "%s / %s (%d%%)" % (
            human_bytes(memory.used),
            human_bytes(memory.total),
            int(round(percent(memory.used, memory.total))),
        ))],
        [],
        [("class:panel.italic", "按类别统计")],
    ]
    for category in cats:
        value_pct = percent(category.bytes, memory.total)
        legend_lines.append([
            ("class:waffle." + category.key, glyph),
            ("class:panel.body", " " + pad_display(category.label, 6)),
            ("class:panel.value", human_bytes(category.bytes)),
            ("class:panel.muted", "  %4.1f%%" % value_pct),
        ])

    if width and width < 64:
        return waffle_lines + [[]] + legend_lines

    left_width = max(
        (sum(display_width(text) for _, text in line) for line in waffle_lines),
        default=19,
    ) + 4
    composed = []
    for index in range(max(len(waffle_lines), len(legend_lines))):
        line = []
        if index < len(waffle_lines):
            line.extend(waffle_lines[index])
            current = sum(display_width(text) for _, text in waffle_lines[index])
            line.append(("", " " * max(0, left_width - current)))
        else:
            line.append(("", " " * left_width))
        if index < len(legend_lines):
            line.extend(legend_lines[index])
        composed.append(line)
    return composed


def build_panel_lines(
    snapshot: StatusSnapshot,
    glyphs: Dict[str, object],
    width: int,
) -> List[Line]:
    lines = [
        [("class:panel.title", "系统上下文")],
        [("class:panel.muted", "wocli v%s · %s · %s · %d 核 · Python %s" % (
            snapshot.version,
            system_label(snapshot.system),
            snapshot.system.machine,
            snapshot.system.cores,
            snapshot.system.python,
        ))],
    ]
    lines.extend(_memory_block(snapshot, glyphs, width))

    cpu = snapshot.cpu
    if cpu is not None and cpu.percent is not None:
        body = [("class:panel.value", "%d%%" % int(round(cpu.percent)))]
        if cpu.cores:
            body.append(("class:panel.muted", " · %d 核" % cpu.cores))
        if cpu.load is not None:
            body.append(("class:panel.muted", " · 负载 %.2f / %.2f / %.2f" % cpu.load))
        if cpu.percent >= 85:
            body[0] = ("class:panel.bad", body[0][1])
        elif cpu.percent >= 60:
            body[0] = ("class:panel.warn", body[0][1])
    else:
        body = [("class:panel.muted", "未获取到")]
    lines.extend(_section("CPU", "/sys", body, glyphs))

    disk = snapshot.disk
    if disk is not None:
        body = [
            ("class:panel.value", "%s / %s" % (
                human_bytes(disk.used), human_bytes(disk.total),
            )),
            ("class:panel.muted", " (%d%%) · 剩余 %s" % (
                int(round(percent(disk.used, disk.total))),
                human_bytes(max(0, disk.total - disk.used)),
            )),
        ]
    else:
        body = [("class:panel.muted", "未获取到")]
    lines.extend(_section("磁盘", "/sys", body, glyphs))

    battery = snapshot.battery
    if battery is not None:
        body = [
            ("class:panel.good", "%s %d%%" % (
                battery_glyph(battery.percent, bool(glyphs.get("unicode", True))),
                battery.percent,
            )),
            ("class:panel.muted", " · %s" % battery.status),
        ]
        if battery.health is not None:
            body.append(("class:panel.muted", " · 健康 %d%%" % battery.health))
        if battery.cycles is not None:
            body.append(("class:panel.muted", " · 循环 %d 次" % battery.cycles))
        if battery.temp is not None:
            body.append(("class:panel.muted", " · %.1f°C" % battery.temp))
    else:
        body = [("class:panel.muted", "未检测到电池（台式机/虚拟机通常没有）")]
    lines.extend(_section("电池", "/battery", body, glyphs))

    wifi = snapshot.wifi
    if wifi is not None and (wifi.ssid or wifi.rssi is not None):
        bars, label = signal_bars(wifi.rssi, bool(glyphs.get("unicode", True)))
        body = [("class:panel.value", wifi.ssid or "WiFi")]
        if wifi.rssi is not None:
            body.append(("class:panel.good", " · %s %s" % (bars, label)))
            body.append(("class:panel.muted", " (%d dBm)" % wifi.rssi))
        if wifi.channel:
            body.append(("class:panel.muted", " · 信道 %s" % wifi.channel))
        if wifi.rate:
            body.append(("class:panel.muted", " · %s" % wifi.rate))
        lines.extend(_section("网络", "/wifi", body, glyphs))
        if wifi.note:
            lines.append([
                ("class:panel.muted", "  " + _display_note(wifi.note, glyphs)),
            ])
    else:
        note = wifi.note if wifi is not None and wifi.note else "正在采集无线信息，或当前未连接"
        lines.extend(_section(
            "网络", "/wifi", [("class:panel.muted", _display_note(note, glyphs))], glyphs,
        ))

    git = snapshot.git
    if git is not None:
        body = [
            ("class:panel.branch", "%s %s" % (glyphs["branch"], git.branch)),
            ("class:panel.muted", " · "),
            ("class:panel.good" if not git.dirty else "class:panel.warn",
             "干净" if not git.dirty else "有改动"),
        ]
        if git.additions or git.deletions:
            body.append(("class:panel.good", " · +%d" % git.additions))
            body.append(("class:panel.bad", " %s%d" % (
                glyphs.get("minus", "−"), git.deletions,
            )))
        if git.untracked:
            body.append(("class:panel.muted", " · %d 个未跟踪" % git.untracked))
    else:
        body = [("class:panel.muted", "不是 Git 仓库")]
    lines.extend(_section(
        "Git",
        shorten(snapshot.cwd, 36, str(glyphs.get("ellipsis", "…"))),
        body,
        glyphs,
    ))
    lines.append([
        ("class:panel.muted", "输入 /status 刷新 · Ctrl+K 命令面板 · Shift+Tab 切换模式"),
    ])
    return lines


# ---------- 帮助 / 诊断 ----------

SHELL_COMMANDS = {
    "status": "系统上下文面板（CPU / 内存 / 电池 / WiFi / Git）",
    "help": "命令列表与快捷键",
    "theme": "切换主题（catppuccin / neon / amber / paper / auto）",
    "mode": "切换人格模式（正常=稳定 / 整活=彩色运势 / 死机=故障风）",
    "doctor": "终端与运行环境诊断",
    "clear": "清屏并重绘欢迎界面",
    "version": "显示版本号",
    "goodbye": "播放花式退出动画，然后退出驾驶舱",
    "quit": "退出驾驶舱（也可以按两次 Ctrl-C）",
}


def all_command_names() -> List[str]:
    names = set(SHELL_COMMANDS) | set(COMMANDS)
    return sorted(names)


def build_help_lines() -> List[Line]:
    lines = [[("class:panel.title", "驾驶舱命令")]]
    for name, description in SHELL_COMMANDS.items():
        lines.append([
            ("class:panel.ref", pad_display("/" + name, 12)),
            ("class:panel.body", description),
        ])
    lines.append([])

    for group, commands in HELP_GROUPS.items():
        visible = [command for command in commands if command in COMMANDS and command != "tui"]
        if not visible:
            continue
        lines.append([("class:panel.title", "[%s]" % group)])
        for command in visible:
            lines.append([
                ("class:panel.ref", pad_display("/" + command, 12)),
                ("class:panel.body", COMMANDS[command][1]),
            ])
        lines.append([])

    lines.append([
        ("class:panel.muted", "命令可以带 / 也可以不带 · Tab 补全 · Ctrl+K 命令面板"),
    ])
    return lines


def build_doctor_lines(
    snapshot: StatusSnapshot,
    mode: str,
    theme: Theme,
    ptk_version: str,
    history_path: str,
    prefs_path: str,
) -> List[Line]:
    caps = terminal.CAPS
    lines = [
        [("class:panel.title", "环境诊断")],
        [("class:panel.body", "wocli v%s" % snapshot.version)],
        [("class:panel.body", "Python %s · %s · %s" % (
            snapshot.system.python,
            system_label(snapshot.system),
            snapshot.system.machine,
        ))],
        [("class:panel.body", "终端: %s · Unicode %s · ANSI %s" % (
            caps.get("color_depth", "none"),
            "yes" if caps.get("unicode") else "no",
            "yes" if caps.get("ansi") else "no",
        ))],
        [("class:panel.body", "prompt_toolkit: %s" % ptk_version)],
        [("class:panel.body", "主题: %s · 模式: %s" % (theme.label, mode_label(mode)))],
        [("class:panel.muted", "历史: %s" % history_path)],
        [("class:panel.muted", "配置: %s" % prefs_path)],
    ]
    return lines


# ---------- 输入解析 / 偏好 ----------

def parse_shell_input(text: str) -> Optional[Tuple[str, List[str]]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        posix = os.name != "nt"
        tokens = shlex.split(text, posix=posix)
        if not posix:
            tokens = [
                token[1:-1]
                if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
                else token
                for token in tokens
            ]
    except ValueError:
        return None
    if not tokens:
        return None
    command = tokens[0]
    if command == "?":
        return "help", []
    if command.startswith("/"):
        command = command[1:]
    if not command:
        return None
    return command.lower(), tokens[1:]


def default_prefs_path() -> str:
    return os.path.expanduser("~/.wocli_tui.json")


def default_history_path() -> str:
    return os.path.expanduser("~/.wocli_history")


def load_prefs(path: Optional[str] = None) -> Dict[str, Optional[str]]:
    path = path or default_prefs_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {"theme": None, "mode": None}
    if not isinstance(data, dict):
        return {"theme": None, "mode": None}
    theme = data.get("theme")
    if not isinstance(theme, str) or (theme not in THEMES and theme != AUTO_THEME):
        theme = None
    mode = normalize_mode(data.get("mode"))
    return {"theme": theme, "mode": mode}


def save_prefs(theme: str, mode: str, path: Optional[str] = None) -> None:
    path = path or default_prefs_path()
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {"theme": theme, "mode": mode},
                handle,
                ensure_ascii=False,
                indent=2,
            )
    except OSError:
        pass
