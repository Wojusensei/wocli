"""wocli - 跨命令共用的工具函数."""

import subprocess


def run_cmd(cmd, timeout=6):
    """执行外部命令并返回 stdout 文本，命令不存在/超时/报错时返回 None.

    统一收口跨平台的外部命令调用：没有超时的话，某个系统工具卡住（比如
    macOS 的 system_profiler）会把整个命令一起拖死；errors="replace" 则保证
    输出不是本机编码（中文 Windows 的 GBK 提示文本等）时也不会崩。
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
    except Exception:
        return None
    return result.stdout


def format_bytes(size_bytes):
    """字节数转人类可读字符串."""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def render_bar(pct, width=30):
    """渲染 '=====>  ' 风格进度条，总宽度恒等于 width，满格时不越界."""
    filled = int(width * min(1.0, max(0.0, pct)))
    if filled >= width:
        return "=" * width
    return "=" * filled + ">" + " " * (width - filled - 1)
