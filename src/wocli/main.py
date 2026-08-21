#!/usr/bin/env python3
"""wocli - Main entry point."""

import os
import sys
from wocli import terminal, __version__

terminal.init_terminal()

from wocli.commands import (
    ip, port, tree, sys_cmd, path_cmd, gpa, luck, matrix,
    lolcat, time_cmd, hash_cmd, regex_cmd, typing_cmd,
    progress, qr_cmd, goodbye, cow, glitch, battery, wifi_cmd,
    dead, chat, dino, badapple
)

COMMANDS = {
    "ip": (ip.run, "查看网络信息 (IPv4/IPv6/网关/公网IP)"),
    "port": (port.run, "查看端口占用"),
    "tree": (tree.run, "树形显示文件夹结构"),
    "sys": (sys_cmd.run, "系统状态 (CPU/内存/磁盘)"),
    "path": (path_cmd.run, "查看 PATH 环境变量"),
    "gpa": (gpa.run, "加权 GPA 计算器"),
    "luck": (luck.run, "每日编程运势"),
    "matrix": (matrix.run, "嘉豪数字雨"),
    "lolcat": (lolcat.run, "彩虹色输出文字"),
    "time": (time_cmd.run, "测试代码运行耗时"),
    "hash": (hash_cmd.run, "计算文件 MD5/SHA256"),
    "regex": (regex_cmd.run, "正则表达式测试器"),
    "typing": (typing_cmd.run, "打字速度测试"),
    "progress": (progress.run, "假进度条"),
    "qr": (qr_cmd.run, "终端生成二维码"),
    "goodbye": (goodbye.run, "花式退出动画"),
    "cow": (cow.run, "ASCII 牛说话"),
    "glitch": (glitch.run, "文字故障风"),
    "battery": (battery.run, "电池信息与健康评分"),
    "wifi": (wifi_cmd.run, "WiFi 信息与信号评分"),
    "dead": (dead.run, "伪装终端死机"),
    "chat": (chat.run, "局域网聊天，和舍友用终端对话"),
    "dino": (dino.run, "终端跑酷小游戏"),
    "badapple": (badapple.run, "播放 Bad Apple ASCII 动画"),
}

HELP_GROUPS = {
    "学习": ["ip", "chat"],
    "效率": ["port", "tree", "sys", "path", "battery", "wifi"],
    "发电": ["gpa", "luck", "matrix", "lolcat", "typing", "progress", "qr", "goodbye", "cow", "glitch", "dead", "dino", "badapple"],
    "coding": ["time", "hash", "regex"]
}


def print_help():
    # 使用 terminal 模块获取自适应 logo
    logo = terminal.get_logo()
    print(logo)
    print()
    print("  用法: wocli <命令> [参数]")
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


def _dispatch():
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

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
        print(f"输入 'wocli help' 查看可用命令。")


if __name__ == "__main__":
    main()