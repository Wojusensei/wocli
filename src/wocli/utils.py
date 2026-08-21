"""wocli - 跨命令共用的工具函数."""


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
