"""wocli dead - 伪装终端死机"""
import sys
import time
import random


def run():
    print()
    print("  !! WARNING: Kernel panic detected !!")
    time.sleep(1)

    # 花屏
    chars = "!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
    colors = [31, 32, 33, 34, 35, 36, 91, 92, 93, 94, 95, 96]
    for _ in range(20):
        line = "  " + "".join(random.choice(chars) for _ in range(60))
        color = random.choice(colors)
        sys.stdout.write(f"\033[{color}m{line}\033[0m\n")
        sys.stdout.flush()
        time.sleep(0.05)

    time.sleep(0.5)

    # 蓝屏
    sys.stdout.write("\033[44m\033[37m")
    sys.stdout.write("\033[2J\033[H")
    print()
    print("  *** SYSTEM ERROR ***")
    print()
    print("  A fatal exception has occurred at 0xDEADBEEF")
    print("  The system has been halted.")
    print()
    print("  Attempting to recover...")
    sys.stdout.flush()

    time.sleep(3)

    # 恢复
    sys.stdout.write("\033[0m\033[2J\033[H")
    sys.stdout.write("  Just kidding. Your terminal is fine.\n\n")
    sys.stdout.flush()