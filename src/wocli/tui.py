"""wocli tui - 驾驶舱入口.

这一层只做参数解析和 TTY 检查；prompt_toolkit 的交互实现放在
``tui_app`` 里延迟导入，这样没装它的时候其它命令不受影响。
"""

import argparse
import sys

from wocli.tui_core import MODE_ALIASES, MODES, THEME_CHOICES


def is_interactive() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wocli tui",
        description="wocli 终端驾驶舱：实时状态栏、系统面板、主题与人格模式",
    )
    parser.add_argument(
        "--theme",
        choices=THEME_CHOICES,
        help="启动时使用的主题（catppuccin / neon / amber / paper / auto）",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(MODES) + tuple(MODE_ALIASES),
        help="启动时的人格模式（正常 / 整活 / 死机）",
    )
    parser.add_argument(
        "--no-boot",
        action="store_true",
        help="跳过开机自检动画",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="强制使用 ASCII 图元（终端字体画不出 ▦ ❯ 这类符号时用）",
    )
    return parser


def run() -> None:
    argv = sys.argv[1:]
    if argv and argv[0].lower() in ("tui", "shell", "cockpit"):
        argv = argv[1:]
    args = build_parser().parse_args(argv)

    if not is_interactive():
        print("wocli tui 需要交互式终端。")
        print("在脚本或管道里请直接用 wocli <命令>，例如 wocli sys。")
        return

    try:
        from wocli.tui_app import run_app
    except ImportError:
        print("wocli tui 需要 prompt_toolkit。")
        print("安装：pip install prompt_toolkit")
        return

    run_app(
        theme_key=args.theme,
        mode=args.mode,
        boot=not args.no_boot,
        ascii_only=args.ascii,
    )
