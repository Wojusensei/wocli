"""wocli count - 统计文本字数 / 单词数."""

import sys

END = "_over_"


def read_text():
    """收集多行输入，直到遇到哨兵。返回行列表。

    为什么用哨兵：终端对换行会当作回车提交，粘贴多行文本会被
    截成多条指令，只能靠哨兵兜住整段。
    """
    print(f"  请输入正文（可多行粘贴），单独一行输入 {END} 结束：")
    lines = []
    try:
        while True:
            line = input("  ")
            if line.strip() == END:
                break
            lines.append(line)
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return lines


def count_cn(lines):
    """中文模式：统计字数."""
    text = "".join(lines).strip()
    if not text:
        print("\n  没输入内容哦。\n")
        return
    print()
    print(f"  字数：{len(text)}")
    print()


def count_en(lines):
    """英文模式：统计单词数."""
    text = " ".join(lines).strip()
    if not text:
        print("\n  没输入内容哦。\n")
        return
    print()
    print(f"  单词数：{len(text.split())}")
    print()


def pick_lang():
    """交互式选择语言。返回 'cn' / 'en' / None(退出)."""
    while True:
        try:
            mode = input("  1.中文 2.英文 0.退出：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if mode == "0":
            print("\n  再见。\n")
            return None
        elif mode == "1":
            return "cn"
        elif mode == "2":
            return "en"
        else:
            print("  无效选择，请重新输入。\n")


def run():
    """运行 count 命令."""
    print()
    print("  [ 文本统计 ]")
    print("  " + "-" * 40)

    lang = None
    if len(sys.argv) >= 2:
        arg = sys.argv[1].lower()
        if arg == "-cn":
            lang = "cn"
        elif arg == "-en":
            lang = "en"
        else:
            print(f"\n  不支持的参数：{arg}（只支持 -cn 和 -en）\n")
            return
    else:
        lang = pick_lang()
        if lang is None:
            return

    lines = read_text()
    if lines is None:
        return

    if lang == "cn":
        count_cn(lines)
    else:
        count_en(lines)
