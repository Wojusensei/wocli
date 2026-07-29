"""wocli goodbye - 花式退出动画."""

import sys
import time
import random


MESSAGES = [
    "明天又是充满 bug 的一天(目移)",
    "记得 commit 和 push 哦",
    "没人觉得 rust 很香吗",
    "就当是为了我，对他使用force-push吧",
    "Goodbye world！",
    "本次编码结束，bug 数 +1。",
    "代码能跑就行...",
    "感谢使用awa",
    "Ctrl+C 的人生不需要解释",
]


def run():
    """运行 goodbye 命令."""
    msg = random.choice(MESSAGES)

    print()
    print("  System will shut down in 3 seconds...")
    time.sleep(1)

    width = 30
    for i in range(width + 1):
        bar = "=" * i + ">" + " " * (width - i)
        pct = int(i / width * 100)
        sys.stdout.write(f"\r  [{bar}] {pct}%")
        sys.stdout.flush()
        time.sleep(0.08)

    print()
    print(f"  {msg}")
    print("  Bye!")
    print()