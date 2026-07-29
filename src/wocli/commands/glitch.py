"""wocli glitch - 文字故障风效果."""

import sys
import random


def glitch_case(text):
    return "".join(
        c.upper() if random.random() > 0.5 else c.lower()
        for c in text
    )


def glitch_leet(text):
    mapping = {
        "a": "4", "A": "4",
        "e": "3", "E": "3",
        "i": "1", "I": "1",
        "o": "0", "O": "0",
        "s": "5", "S": "5",
        "t": "7", "T": "7",
        "l": "1", "L": "1",
    }
    return "".join(mapping.get(c, c) for c in text)


def glitch_zalgo(text):
    up = "".join(random.choice("''^`") for _ in range(len(text)))
    down = "".join(random.choice(",.;:") for _ in range(len(text)))
    return up + "\n" + text + "\n" + down


def glitch_morse(text):
    return " ".join(
        "".join(random.choice([".", "-"]) for _ in range(random.randint(1, 4)))
        for _ in text.split()
    )


def run():
    """运行 glitch 命令."""
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = "Hello World"

    print()
    print(f"  Original : {text}")
    print(f"  Glitch 1 : {glitch_case(text)}")
    print(f"  Glitch 2 : {glitch_leet(text)}")
    print(f"  Glitch 3 : {glitch_zalgo(text)}")
    print()