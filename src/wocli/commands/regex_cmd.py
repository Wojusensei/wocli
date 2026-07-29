"""wocli regex - 正！则！."""

import re
import sys


def run():
    if len(sys.argv) < 2:
        print("\n  用法：wocli regex '<正则表达式>'\n")
        return

    pattern = sys.argv[1]
    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"\n  正则无效：{e}\n")
        return

    print()
    print(f"  表达式：{pattern}")
    print(f"  输入文本（Ctrl+D 结束）：")

    try:
        text = sys.stdin.read().strip()
    except KeyboardInterrupt:
        print()
        return

    if not text:
        print("  未输入文本。\n")
        return

    matches = regex.finditer(text)
    count = 0
    for match in matches:
        count += 1
        print(f"  匹配 {count}：位置 {match.start()}-{match.end()}  {match.group()}")

    print(f"\n  共 {count} 处匹配。\n")