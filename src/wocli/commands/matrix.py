"""wocli matrix - 嘉豪数字雨"""
import random
import sys
import time
import signal
import os

class Matrix:
    def __init__(self, phrases):
        self.phrases = phrases
        self.running = True
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        self.running = False

    def run(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        green = "\033[32m"
        reset = "\033[0m"
        try:
            cols = os.get_terminal_size().columns
        except OSError:
            cols = 80

        drops = [random.randint(0, 20) for _ in range(cols)]
        text_cols = {}

        try:
            while self.running:
                line = ""
                for i in range(cols):
                    if i in text_cols:
                        phrase, idx = text_cols[i]
                        if idx < len(phrase):
                            line += green + phrase[idx] + reset
                            text_cols[i] = (phrase, idx + 1)
                            continue
                        else:
                            del text_cols[i]
                            drops[i] = random.randint(3, 18)

                    if drops[i] == 0:
                        if self.phrases and random.random() < 0.02:
                            phrase = random.choice(self.phrases)
                            text_cols[i] = (phrase, 0)
                            line += green + phrase[0] + reset
                            text_cols[i] = (phrase, 1)
                        else:
                            line += green + random.choice(chars) + reset
                            drops[i] = random.randint(3, 18)
                    else:
                        line += " "
                        drops[i] -= 1

                sys.stdout.write(line + "\n")
                sys.stdout.flush()
                time.sleep(0.05)
        finally:
            sys.stdout.write("\033[?25h")
            sys.stdout.write(reset)
            sys.stdout.flush()
            print()

def run():
    if len(sys.argv) > 1:
        Matrix(sys.argv[1:]).run()
    else:
        Matrix([]).run()