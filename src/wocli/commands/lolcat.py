"""wocli lolcat - 彩虹色输出文字."""

import sys


def rainbow(text):
    """给文字加上彩虹渐变色."""
    colors = [196, 202, 208, 214, 220, 226, 190, 154, 118, 82, 46, 47, 48, 49, 50, 51, 45, 39, 33, 27, 21, 57, 93, 129, 165, 201]
    result = ""
    for i, char in enumerate(text):
        if char == " ":
            result += " "
        else:
            color = colors[i % len(colors)]
            result += f"\033[38;5;{color}m{char}\033[0m"
    return result


def run():
    """运行 lolcat 命令."""
    if len(sys.argv) < 2:
        if not sys.stdin.isatty():
            text = sys.stdin.read().strip()
        else:
            text = "Hello, wocli!"
    else:
        text = " ".join(sys.argv[1:])

    print(rainbow(text))

    # 这个简单啊。