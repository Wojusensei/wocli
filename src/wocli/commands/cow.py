"""wocli cow - ASCII 牛说话"""
import sys
from wocli import terminal

COW_UNICODE = r"""
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
"""

COW_ASCII = r"""
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||
"""

def make_bubble(text):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        if len(line) + len(word) + 1 <= 36:
            line += (" " + word) if line else word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    max_len = max((len(l) for l in lines), default=0)
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
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "哞。(无感情)"
    if terminal.CAPS.get("unicode", True):
        cow = COW_UNICODE
    else:
        cow = COW_ASCII

    print()
    print(make_bubble(text))
    print(cow)
    print()