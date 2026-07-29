"""wocli matrix - 我是嘉豪."""

import random
import sys
import time
import signal
import shutil
import os


class Matrix:
    def __init__(self):
        self.columns = 0
        self.lines = 0
        self.drops = []
        self.running = True
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        self.running = False

    def init_terminal(self):
        """获取终端尺寸，初始化掉落位置."""
        try:
            size = shutil.get_terminal_size()
        except Exception:
            size = os.terminal_size((80, 24))
        self.columns = size.columns
        self.lines = size.lines
        self.drops = [random.randint(0, self.lines) for _ in range(self.columns)]

    def run(self):
        # 隐藏光标
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        self.init_terminal()

        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        green = "\033[32m"
        bright = "\033[1;32m"
        reset = "\033[0m"

        try:
            while self.running:
                line = ""
                for i in range(self.columns):
                    if self.drops[i] == 0:
                        # 新字符
                        line += bright + random.choice(chars) + reset
                        self.drops[i] = random.randint(3, 18)
                    elif 0 < self.drops[i] <= 3:
                        # 刚掉下来的普通绿
                        line += green + random.choice(chars) + reset
                        self.drops[i] -= 1
                    else:
                        line += " "
                        self.drops[i] -= 1

                sys.stdout.write(line + "\n")
                sys.stdout.flush()
                time.sleep(0.05)

                # 芝士重新检查终端大小的地方
                self.init_terminal()
        except Exception:
            pass
        finally:
            # 恢复光标
            sys.stdout.write("\033[?25h")
            sys.stdout.write(reset)
            sys.stdout.flush()


def run():
    m = Matrix()
    m.run()