"""wocli cow - ASCII牛说你说的话."""

import sys


COW = r"""
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
"""


def make_bubble(text):
    """生成对话气泡."""
    lines = []
    words = text.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 <= 36:
            line += (" " + word) if line else word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    max_len = max(len(l) for l in lines) if lines else 0
    top = "  " + "_" * (max_len + 2)
    bottom = "  " + "-" * (max_len + 2)

    bubble = [top]
    if len(lines) == 1:
        bubble.append(f" < {lines[0]} >")
    else:
        for i, l in enumerate(lines):
            if i == 0:
                bubble.append(f" / {l:<{max_len}} \\")
            elif i == len(lines) - 1:
                bubble.append(f" \\ {l:<{max_len}} /")
            else:
                bubble.append(f" | {l:<{max_len}} |")
    bubble.append(bottom)
    return "\n".join(bubble)


def run():
    """运行 cow 命令."""
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "哞————(无意味)"

    print()
    print(make_bubble(text))
    print(COW)
    print()