"""wocli 命令注册表.

CLI (`wocli <命令>`) 和驾驶舱 TUI 都用这一份表，避免两处各维护一份命令列表。
TUI 入口在这里做延迟导入：没装 prompt_toolkit 时其它命令仍然能用。
"""

from wocli.commands import (
    badapple,
    battery,
    chat,
    count_cmd,
    cow,
    dead,
    glitch,
    goodbye,
    gpa,
    hash_cmd,
    ip,
    lolcat,
    luck,
    matrix,
    path_cmd,
    port,
    progress,
    qr_cmd,
    regex_cmd,
    sys_cmd,
    time_cmd,
    tree,
    typing_cmd,
    wifi_cmd,
)


def run_tui():
    """打开驾驶舱 TUI（延迟导入，prompt_toolkit 缺失时给出可读提示）."""
    from wocli.tui import run as run_tui_app

    run_tui_app()


COMMANDS = {
    "tui": (run_tui, "驾驶舱 TUI（实时状态栏 / 系统面板 / 主题）"),
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
    "badapple": (badapple.run, "播放 Bad Apple ASCII 动画"),
    "count": (count_cmd.run, "统计文本字数/单词数 (-cn 中文字数 / -en 英文单词数)"),
}

# 只在 CLI 层生效的别名，不重复出现在补全菜单里
ALIASES = {
    "shell": "tui",
    "cockpit": "tui",
}

HELP_GROUPS = {
    "学习": ["ip", "chat"],
    "效率": ["tui", "port", "tree", "sys", "path", "battery", "wifi", "count"],
    "发电": [
        "gpa", "luck", "matrix", "lolcat", "typing", "progress", "qr",
        "goodbye", "cow", "glitch", "dead", "badapple",
    ],
    "coding": ["time", "hash", "regex"],
}
