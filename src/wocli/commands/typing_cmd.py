"""wocli typing - 终端打字速度测试."""

import time
import sys
import random


SAMPLE_TEXTS = [
    "The quick brown fox jumps over the lazy dog",
    "Pack my box with five dozen liquor jugs",
    "How vexingly quick daft zebras jump",
    "The five boxing wizards jump quickly",
    "Sphinx of black quartz, judge my vow",
    "Two driven jocks help fax my big quiz",
    "Bright vixens jump; dozy fowl quack",
    "A quick movement of the enemy will jeopardize six gunboats",
    "All questions asked by five watch experts amazed the judge",
    "Grumpy wizards make toxic brew for the evil queen and jack",
]


def run():
    """运行 typing 命令."""
    text = random.choice(SAMPLE_TEXTS)

    print()
    print("  [ 打字速度测试 ]")
    print("  " + "-" * 40)
    print(f"  请打出以下文字:")
    print(f"  \"{text}\"")
    print()

    input("  按 Enter 开始计时...")

    start = time.time()
    try:
        user_input = input("  > ")
    except (KeyboardInterrupt, EOFError):
        print("\n  已取消。\n")
        return
    end = time.time()

    elapsed = end - start
    correct_chars = sum(1 for a, b in zip(user_input, text) if a == b)
    accuracy = correct_chars / len(text) * 100 if text else 0
    word_count = len(text.split())
    minutes = elapsed / 60
    wpm = word_count / minutes if minutes > 0 else 0

    print()
    print("  " + "-" * 40)
    print(f"  用时: {elapsed:.1f} 秒")
    print(f"  正确字符数: {correct_chars}/{len(text)} ({accuracy:.0f}%)")
    print(f"  速度: {wpm:.0f} WPM")

    # 评级
    if wpm >= 80:
        level = "你跟这个发电cli的神经开发者一个打字速度"
    elif wpm >= 60:
        level = "你是个正常人！"
    elif wpm >= 40:
        level = "哦兄弟你要继续加油了"
    elif wpm >= 20:
        level = "二指禅？？？"
    else:
        level = "一只手打字很累吧。"

    print(f"  评级: {level}")
    print()