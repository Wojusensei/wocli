"""wocli dead - 伪装终端死机"""
import sys
import time
import random
from wocli import terminal

def run(): # 修复一下蓝屏消失的问题
    print("\n  !! WARNING: Kernel panic detected !!")
    time.sleep(1)

    chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    colors = [31, 32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96]
    for _ in range(20):
        line = "  " + "".join(random.choice(chars) for _ in range(60))
        if terminal.CAPS["color_depth"] != "none":
            color = random.choice(colors)
            sys.stdout.write(f"\033[{color}m{line}\033[0m\n")
        else:
            sys.stdout.write(line + "\n")
        sys.stdout.flush()
        time.sleep(0.05)

    time.sleep(0.5)

    # 不触发 autoreset
    if terminal.CAPS["ansi"]:
        sys.stdout.write("\033[44m\033[37m")
    terminal.clear_screen()

    # 避免 colorama 自动重置背景色
    sys.stdout.write("\n")
    sys.stdout.write("  *** SYSTEM ERROR ***\n")
    sys.stdout.write("\n")
    sys.stdout.write("  A fatal exception has occurred at 0xDEADBEEF\n")
    sys.stdout.write("  The system has been halted.\n")
    sys.stdout.write("\n")
    sys.stdout.write("  Attempting to recover...\n")
    sys.stdout.flush()
    time.sleep(3)

    # 恢复代码
    if terminal.CAPS["ansi"]:
        sys.stdout.write("\033[0m")
    terminal.clear_screen()
    sys.stdout.write("  Just kidding. Your terminal is fine.\n\n")
    sys.stdout.flush()