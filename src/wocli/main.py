#!/usr/bin/env python3
"""wocli - Main entry point."""

import sys

from wocli.commands import (
    ip, port, tree, sys_cmd, path_cmd, gpa, luck, matrix,
    lolcat, time_cmd, hash_cmd, regex_cmd, typing_cmd,
    progress, qr_cmd, goodbye, cow, glitch, battery, wifi_cmd, dead,chat
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
}

HELP_GROUPS = {
    
    "学习": ["ip","chat"],
    "效率": ["port", "tree", "sys", "path", "battery", "wifi"],
    "发电": ["gpa", "luck", "matrix", "lolcat", "typing", "progress", "qr", "goodbye", "cow", "glitch", "dead"],
    "coding": ["time", "hash", "regex"]

}


def print_help():
    colors = [196, 202, 208, 214, 220, 226]
    blocks = [
        "██╗    ██╗       ██████╗       ██████╗      ██╗         ██╗",
        "██║    ██║     ██╔═══██╗     ██╔════╝      ██║         ██║",
        "██║ █╗ ██║     ██║   ██║     ██║           ██║         ██║",
        "██║███╗██║     ██║   ██║     ██║           ██║         ██║",
        "╚███╔███╔╝     ╚██████╔╝     ╚██████╗      ███████╗    ██║",
        " ╚══╝╚══╝       ╚═════╝       ╚═════╝      ╚══════╝    ╚═╝",
    ]
    shadow = [
        "                                                              ",
        "   ██╗    ██╗       ██████╗       ██████╗      ██╗         ██╗  ",
        "   ██║    ██║     ██╔═══██╗     ██╔════╝      ██║         ██║  ",
        "   ██║ █╗ ██║     ██║   ██║     ██║           ██║         ██║  ",
        "   ██║███╗██║     ██║   ██║     ██║           ██║         ██║  ",
        "   ╚███╔███╔╝     ╚██████╔╝     ╚██████╗      ███████╗    ██║  ",
        "    ╚══╝╚══╝       ╚═════╝       ╚═════╝      ╚══════╝    ╚═╝  ",
    ]

    print()

    for line in shadow:
        for ch in line:
            if ch.strip():
                sys.stdout.write(f"\033[38;5;240m{ch}\033[0m")
            else:
                sys.stdout.write(ch)
        print()


    sys.stdout.write(f"\033[8A")


    for row_idx, line in enumerate(blocks):
        color = colors[row_idx % len(colors)]
        for ch in line:
            if ch.strip():
                sys.stdout.write(f"\033[38;5;{color}m{ch}\033[0m")
            else:
                sys.stdout.write(ch)
        print()


    for _ in range(len(shadow) - len(blocks)):
        print()

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
    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command in ("help", "-h", "--help"):
        print_help()
        return

    if command in ("version", "-v", "--version"):
        print(f"wocli v0.1.0")
        return

    if command in COMMANDS:
        sys.argv = sys.argv[1:]
        COMMANDS[command][0]()
    else:
        print(f"未知命令: {command}")
        print(f"输入 'wocli help' 查看可用命令。")


if __name__ == "__main__":
    main()