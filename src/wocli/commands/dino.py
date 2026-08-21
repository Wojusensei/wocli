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
            return ch.decode('utf-8', errors='ignore')
        return ''
else:
    import termios, tty, select
    _old_term = None
    _fd = sys.stdin.fileno()

    def setup_terminal():
        global _old_term
        _old_term = termios.tcgetattr(_fd)
        tty.setraw(_fd)
        # 注意：绝不能给 _fd 设 O_NONBLOCK——stdin/stdout 常共享同一个终端
        # 文件描述，非阻塞会让大块渲染输出抛 BlockingIOError。
        # 按键检测用 select 轮询完成。

    def restore_terminal():
        if _old_term is not None:
            termios.tcsetattr(_fd, termios.TCSADRAIN, _old_term)

    def get_key():
        r, _, _ = select.select([_fd], [], [], 0)
        if not r:
            return ''
        try:
            return os.read(_fd, 1).decode('utf-8', errors='ignore')
        except OSError:
            return ''

class Game:
    def __init__(self):
        self.high = self._load_high()
        self.ground_y = GROUND - len(CLAUDE_A)
        self._hide_cursor()
        signal.signal(signal.SIGINT, self._stop)
        signal.signal(signal.SIGTERM, self._stop)
        self.reset()

    def reset(self):
        self.score = 0
        self.y = float(self.ground_y)
        self.vy = 0.0
        self.objs = []
        self.speed = 1.1
        self.frame = 0
        self.over = False
        self._want_quit = False

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
        except (OSError, ValueError):
            return 0

    def _save_high(self):
        if self.score > self.high:
            self.high = self.score
            p = os.path.expanduser("~/.wocli_dino")
            try:
                with open(p, "w") as f:
                    f.write(str(self.score))
            except OSError:
                pass

    def jump(self):
        if self.vy == 0 and self.y >= self.ground_y:
            # 初速 2.4 / 重力 0.29 → 跳高约 10 行、滞空约 16 帧，
            # 起跳窗口约 4 列，速度加快后余量更宽
            self.vy = -2.4

    def update(self):
        if self.over:
            return
        self.frame += 1
        self.score += 1
        if self.score % 600 == 0:
            self.speed = min(2.0, self.speed * 1.05)

        self.vy += 0.29
        self.y += self.vy
        if self.y >= self.ground_y:
            self.y = self.ground_y
            self.vy = 0

        # 移除超出屏幕的障碍
        self.objs = [o for o in self.objs if o[0] > -15]
        for o in self.objs:
            o[0] -= self.speed

        # 生成障碍（空列表时直接允许生成，否则场上永远不会有第一个障碍）
        if len(self.objs) < 3 and random.random() < 0.02:
            last_x = max((o[0] for o in self.objs), default=-1)
            if last_x < W - 20:
                if random.random() < 0.65:
                    h = random.randint(2, 3)
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

        # 碰撞检测（小人的图形实体在 X0+1 起宽 4 列，比整行更贴合）
        claude_h = len(CLAUDE_A)
        cx0, cy0 = X0 + 1, int(self.y)
        claude_w = 4
        for ox, ow, oh, oy, _, _ in self.objs:
            iox = int(ox)  # 障碍按浮点速度移动，判定按整列对齐
            if (cx0 + claude_w > iox and cx0 < iox + ow and
                cy0 + claude_h > oy and cy0 < oy + oh):
                self.over = True
                self._save_high()
                break

    def render(self):
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
            iox = int(ox)  # 浮点 x 坐标取整后再做格子索引
            for sy, row in enumerate(shape):
                y = oy + sy
                if 0 <= y < H:
                    for sx, ch in enumerate(row):
                        x = iox + sx
                        if 0 <= x < W and ch != " ":
                            buf[y][x] = f"{col}{ch}{C_RESET}"

        # 只把光标移回左上角整屏覆盖重绘，不做 2J 全清屏（消除闪烁）
        out = ["\033[H"]
        out.extend(" " + "".join(row) for row in buf)
        score_str = f"Score: {self.score:05d}   High: {self.high:05d}"
        hint = "Space:Jump  Q:Quit" if not self.over else "GAME OVER  R:Restart  Q:Quit"
        out.append(f"  {C_ORANGE}{score_str}{C_RESET}    {hint}")
        sys.stdout.write("\n".join(out))
        sys.stdout.flush()

    def input_handle(self):
        while True:
            k = get_key()
            if not k:
                break
            if k == ' ':
                self.jump()
            elif k in ('q', '\x03'):  # raw 模式下 Ctrl+C 读到的是 \x03
                self.over = True
                self._want_quit = True

    def run(self):
        try:
            sys.stdout.write("\033[2J")
            sys.stdout.flush()
            next_t = time.monotonic()
            while True:
                while not self.over:
                    self.input_handle()
                    self.update()
                    self.render()
                    next_t += 0.04
                    time.sleep(max(0.0, next_t - time.monotonic()))
                if self._want_quit:
                    return
                self.render()
                # 游戏结束后等待 R 重开或 Q 退出
                while True:
                    k = get_key()
                    if k == 'r':
                        self._save_high()
                        self.reset()
                        next_t = time.monotonic()
                        break
                    if k in ('q', '\x03'):
                        return
                    time.sleep(0.02)
        finally:
            self._show_cursor()
            self._save_high()


def run():
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("\n  dino 需要在交互式终端里运行。\n")
        return

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
    run()