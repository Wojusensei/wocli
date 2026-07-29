"""wocli regex - 正！则！."""

import re
import sys


def run():
    """运行 regex 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli regex '<正则表达式>'\n")
        return

    pattern = sys.argv[1]

    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"\n  正则表达式无效: {e}\n")
        return

    print()
    print(f"  [ 正则测试 ]")
    print(f"  表达式: {pattern}")
    print(f"  输入文本 (Ctrl+D 结束):")
    print()

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
        start = match.start()
        end = match.end()
        matched = match.group()
        # 显示上下文
        ctx_start = max(0, start - 20)
        ctx_end = min(len(text), end + 20)
        prefix = text[ctx_start:start]
        suffix = text[end:ctx_end]
        ctx = f"{prefix}[{matched}]{suffix}"
        print(f"  匹配 {count}: 位置 {start}-{end}  ->  {ctx}")

    if count == 0:
        print("  无匹配结果。")
    else:
        print(f"\n  共找到 {count} 处匹配。")
    print()