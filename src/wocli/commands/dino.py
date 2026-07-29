import sys, os, time, random, platform, signal

W, H = 70, 20
GROUND = H - 3
X0 = 10
C_ORANGE = "\033[38;5;214m"
C_GREEN  = "\033[32m"
C_WHITE  = "\033[97m"
C_RESET  = "\033[0m"

CLAUDE_A = [" ▗ ▗  ", "  ▘▘  ", "  ▝▝  "]
CLAUDE_B = [" ▖ ▖  ", "  ▝▝  ", "  ▘▘  "]

# ---------- 跨平台终端控制 ----------
if platform.system() == "Windows":
    import msvcrt
    def setup_terminal(): pass
    def restore_terminal(): pass
    def get_key():
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b'\xe0': return ''
            try:
                return ch.decode('utf-8', errors='ignore')
            except:
                return ''
        return ''
else:
    import termios, tty, fcntl
    _old_term = None
    _old_flags = None
    _fd = sys.stdin.fileno()

    def setup_terminal():
        global _old_term, _old_flags
        _old_term = termios.tcgetattr(_fd)
        _old_flags = fcntl.fcntl(_fd, fcntl.F_GETFL)
        tty.setraw(_fd)
        fcntl.fcntl(_fd, fcntl.F_SETFL, _old_flags | os.O_NONBLOCK)

    def restore_terminal():
        if _old_term is not None:
            termios.tcsetattr(_fd, termios.TCSADRAIN, _old_term)
        if _old_flags is not None:
            fcntl.fcntl(_fd, fcntl.F_SETFL, _old_flags)

    def get_key():
        try:
            data = os.read(_fd, 1).decode('utf-8', errors='ignore')
            return data
        except BlockingIOError:
            return ''

class Game:
    def __init__(self):
        self.score = 0
        self.high = self._load_high()
        self.ground_y = GROUND - len(CLAUDE_A)
        self.y = float(self.ground_y)
        self.vy = 0.0
        self.objs = []
        self.speed = 0.8
        self.frame = 0
        self.over = False
        self._hide_cursor()
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, *args):
        self.over = True

    def _hide_cursor(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def _show_cursor(self):
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def _load_high(self):
        p = os.path.expanduser("~/.wocli_dino")
        try:
            with open(p) as f:
                return int(f.read())
        except:
            return 0

    def _save_high(self):
        if self.score > self.high:
            self.high = self.score
            p = os.path.expanduser("~/.wocli_dino")
            try:
                with open(p, "w") as f:
                    f.write(str(self.score))
            except:
                pass

    def jump(self):
        if self.vy == 0 and self.y >= self.ground_y:
            self.vy = -2.2

    def update(self):
        if self.over:
            return
        self.frame += 1
        self.score += 1
        if self.score % 600 == 0:
            self.speed = min(2.0, self.speed * 1.05)

        self.vy += 0.2
        self.y += self.vy
        if self.y >= self.ground_y:
            self.y = self.ground_y
            self.vy = 0

        # 移除超出屏幕的障碍
        self.objs = [o for o in self.objs if o[0] > -15]
        for o in self.objs:
            o[0] -= self.speed

        # 生成障碍
        if len(self.objs) < 3 and random.random() < 0.02:
            last_x = max([o[0] for o in self.objs]) if self.objs else W
            if last_x < W - 20:
                if random.random() < 0.65:
                    h = random.randint(3, 4)
                    w = random.randint(5, 7)
                    cactus = []
                    for i in range(h):
                        line = ""
                        for j in range(w):
                            if i == 0 and j == w // 2: line += "┃"
                            elif i > 0 and (j == 0 or j == w - 1): line += "│"
                            elif i == h - 1: line += "━"
                            else: line += " " if random.random() < 0.7 else "╻"
                        cactus.append(line)
                    self.objs.append([W, w, h, GROUND - h, cactus, C_GREEN])
                else:
                    bird_y = GROUND - random.randint(4, 7)
                    bird = ["  ^^  ", " <^^> "]
                    self.objs.append([W, 6, 2, bird_y, bird, C_WHITE])

        # 碰撞检测
        claude_h = len(CLAUDE_A)
        claude_w = max(len(r) for r in CLAUDE_A)
        cx0, cy0 = X0, int(self.y)
        for ox, ow, oh, oy, _, _ in self.objs:
            if (cx0 + claude_w > ox and cx0 < ox + ow and
                cy0 + claude_h > oy and cy0 < oy + oh):
                self.over = True
                self._save_high()
                break

    def render(self):
        sys.stdout.write("\033[2J\033[H")
        buf = [[" "] * W for _ in range(H)]
        for x in range(W):
            buf[GROUND][x] = "─"

        frame_char = CLAUDE_A if (self.frame // 3) % 2 == 0 else CLAUDE_B
        for dy, row in enumerate(frame_char):
            y = int(self.y) + dy
            if 0 <= y < H:
                for dx, ch in enumerate(row):
                    x = X0 + dx
                    if 0 <= x < W and ch != " ":
                        buf[y][x] = f"{C_ORANGE}{ch}{C_RESET}"

        for ox, ow, oh, oy, shape, col in self.objs:
            for sy, row in enumerate(shape):
                y = oy + sy
                if 0 <= y < H:
                    for sx, ch in enumerate(row):
                        x = ox + sx
                        if 0 <= x < W and ch != " ":
                            buf[y][x] = f"{col}{ch}{C_RESET}"

        for row in buf:
            print(" " + "".join(row))

        score_str = f"Score: {self.score:05d}   High: {self.high:05d}"
        hint = "Space:Jump  Q:Quit" if not self.over else "GAME OVER  R:Restart  Q:Quit"
        print(f"  {C_ORANGE}{score_str}{C_RESET}    {hint}")

    def input_handle(self):
        k = get_key()
        while k:
            if k == ' ':
                self.jump()
            elif k == 'q':
                self.over = True
            elif k == 'r' and self.over:
                self._save_high()
                self.__init__()
            k = get_key()

    def run(self):
        try:
            while not self.over:
                self.input_handle()
                self.update()
                self.render()
                time.sleep(0.04)
            self.render()
            time.sleep(1.5)
        finally:
            self._show_cursor()
            self._save_high()


def main():
    print(f"\n  {C_ORANGE}╭─ Claude Run ──────────────────────────────╮{C_RESET}")
    print(f"  {C_ORANGE}│{C_RESET}  橙色小人跑酷，按任意键开始            {C_ORANGE}│{C_RESET}")
    print(f"  {C_ORANGE}╰──────────────────────────────────────────╯{C_RESET}")

    setup_terminal()
    try:
        # 等待任意键
        while True:
            if get_key():
                break
            time.sleep(0.05)
        g = Game()
        g.run()
    finally:
        restore_terminal()

if __name__ == "__main__":
    main()