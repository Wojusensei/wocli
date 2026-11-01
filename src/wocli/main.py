#!/usr/bin/env python3
"""wocli - Main entry point."""

import os
import sys
from wocli import terminal, __version__

terminal.init_terminal()

from wocli.commands import (  # noqa: F401  保留旧路径导入
    ip, port, tree, sys_cmd, path_cmd, gpa, luck, matrix,
    lolcat, time_cmd, hash_cmd, regex_cmd, typing_cmd,
    progress, qr_cmd, goodbye, cow, glitch, battery, wifi_cmd,
    dead, chat, badapple, count_cmd
)
from wocli.registry import ALIASES, COMMANDS, HELP_GROUPS


def print_help():
    # 使用 terminal 模块获取自适应 logo
    logo = terminal.get_logo()
    print(logo)
    print()
    print("  用法: wocli <命令> [参数]")
    print("  驾驶舱: 直接运行 wocli（WOCLI_NO_TUI=1 可回到这个帮助页）")
    print()

    for group, cmds in HELP_GROUPS.items():
        print(f"  [{group}]")
        for cmd in cmds:
            if cmd in COMMANDS:
                print(f"    {cmd:<12} {COMMANDS[cmd][1]}")
        print()


def main():
    try:
        _dispatch()
    except BrokenPipeError:
        # 管道下游提前关闭（如 wocli path | head），静默退出
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        raise SystemExit(0)
    except KeyboardInterrupt:
        # 各命令内部没拦的 Ctrl+C 在这里兜底，不打堆栈
        print("\n  已退出。")
        raise SystemExit(130)


def _should_launch_tui():
    """没有子命令时：TTY 下默认进驾驶舱，管道/脚本里仍然打印帮助."""
    if os.environ.get("WOCLI_NO_TUI", "").lower() in ("1", "true", "yes"):
        return False
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


TUI_OPTIONS = ("--theme", "--mode", "--no-boot", "--ascii")


def _is_tui_option(argument):
    return any(
        argument == option or argument.startswith(option + "=")
        for option in TUI_OPTIONS
    )


def _dispatch():
    if len(sys.argv) < 2:
        if _should_launch_tui():
            sys.argv = [sys.argv[0], "tui"]
        else:
            print_help()
            return
    elif _is_tui_option(sys.argv[1]):
        # wocli --theme neon 和 wocli tui --theme neon 等价
        sys.argv = [sys.argv[0], "tui"] + sys.argv[1:]

    command = sys.argv[1].lower()
    command = ALIASES.get(command, command)

    if command in ("help", "-h", "--help"):
        print_help()
        return

    if command in ("version", "-v", "--version"):
        print(f"wocli v{__version__}")
        return

    if command in COMMANDS:
        sys.argv = sys.argv[1:]
        COMMANDS[command][0]()
    else:
        print(f"未知命令: {command}")
        print("输入 'wocli help' 查看可用命令。")


if __name__ == "__main__":
    main()