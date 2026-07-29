"""wocli luck - 每日编程运势."""

import random
import datetime


def run():
    """运行 luck 命令."""
    today = datetime.date.today()

    fortunes = [
        ("大吉", 5, "Rust", "？！难道他真的是编译神？！"),
        ("吉", 4, "JavaScript", "bug 会有的，但 It works on my machineeeeee"),
        ("小吉", 3, "C", "指针不野，段不错误。"),
        ("末吉", 2, "Java", "NullPointerException 消失了！"),
        ("凶", 1, "PHP", "今天适合注释旧代码。"),
        ("大凶", 0, "Brainfuck", "别开机。出去走走。"),
    ]

    fortune = random.choice(fortunes)
    name, stars, lang, tip = fortune
    star_str = "*" * stars + "-" * (5 - stars)

    bug_index = random.randint(0, 100)
    bugs = random.randint(0, 15) if bug_index < 50 else random.randint(16, 50)

    yi = random.choice(["写注释", "备份代码", "重构", "摸鱼", "刷LeetCode", "帮室友debug"])
    ji = random.choice(["rm -rf /", "熬夜到三点", "不看文档直接写", "git push --force", "在生产环境测试", "复制粘贴StackOverflow"])

    print()
    print(f"  日期：{today}")
    print(f"  运势：{name} {star_str}")
    print(f"  幸运语言：{lang}")
    print(f"  Bug 指数：{bug_index}%（预计 {bugs} 个 bug）")
    print(f"  宜：{yi}")
    print(f"  忌：{ji}")
    print(f"  {tip}")
    print()