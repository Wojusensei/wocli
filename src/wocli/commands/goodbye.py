"""wocli goodbye - 花式退出动画"""
import sys
import time
import random
from wocli import terminal
from wocli.utils import render_bar

MESSAGES = [
    "明天又是充满 bug 的一天",
    "记得 commit 和 push",
    "没人觉得 rust 很好用吗",
    "就当是为了我，再写一个 demo 吧",
    "再见，世界。",
    "本次编码结束，bug 数 +1。",
    "代码能跑就行，何须理会春秋笔",
    "你的 PR 被拒啦！",
    "Ctrl+C 的人生不需要解释。",
]

def run():
    msg = random.choice(MESSAGES)
    print()
    print("  System will shut down in 3 seconds...")
    time.sleep(1)
    terminal.hide_cursor()

    width = 30
    for i in range(width + 1):
        pct = int(i / width * 100)
        sys.stdout.write(f"\r  [{render_bar(i / width, width)}] {pct}%")
        sys.stdout.flush()
        time.sleep(0.08)

    print()
    print(f"  {msg}")
    print("  Bye!")
    terminal.show_cursor()
    print()