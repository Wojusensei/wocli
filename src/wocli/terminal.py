"""这个模块我用来实现终端能力检测与跨平台渲染适配的功能，解决一下之前的显示问题"""
import sys
import os
import platform
from colorama import init, Fore, Back, Style

# 全局能力标志
CAPS = {
    "color_depth": "none",   # truecolor, 256, 16, none
    "unicode": True,
    "ansi": False,
}

def init_terminal():
    init(autoreset=False)   # 如果您在准备 PR 的时候发现了这一行，我移除了 colorama 自动重置颜色，你可以按需更改

    global CAPS

    # ANSI test
    if platform.system() == "Windows":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            if mode.value & 0x0004:  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                CAPS["ansi"] = True
            else:
                mode.value |= 0x0004
                kernel32.SetConsoleMode(handle, mode)
                CAPS["ansi"] = True
        except Exception:
            CAPS["ansi"] = False
    else:
        # 非 Windows 默认支持 ANSI ？
        CAPS["ansi"] = True

    if CAPS["ansi"]:
        colorterm = os.environ.get("COLORTERM", "")
        term = os.environ.get("TERM", "")
        if "truecolor" in colorterm or "24bit" in colorterm:
            CAPS["color_depth"] = "truecolor"
        elif "256color" in term or "256" in colorterm:
            CAPS["color_depth"] = "256"
        elif platform.system() == "Darwin":
            CAPS["color_depth"] = "truecolor"  # macOS Terminal 是支持真彩的，这里我打算直接用
        elif platform.system() == "Windows":
            # Windows 10 1703+ 支持 24 位色，但 colorama 可能限制到多少我不知道，有 PR 的可以帮忙看看
            CAPS["color_depth"] = "256"
        else:
            # 其他 Linux 或不确定，设为 16 色先
            CAPS["color_depth"] = "16"
    else:
        CAPS["color_depth"] = "none"
    if platform.system() == "Windows" and not CAPS["ansi"]:
        CAPS["unicode"] = False
    else:
        CAPS["unicode"] = True


def colored(text, r=None, g=None, b=None, ansi_code=None):
    if CAPS["color_depth"] == "none":
        return text

    if ansi_code is not None:
        if CAPS["color_depth"] in ("truecolor", "256"):
            return f"\033[38;5;{ansi_code}m{text}\033[0m"
        elif CAPS["color_depth"] == "16":
            base = ansi_code % 16 if ansi_code < 256 else 7
            return f"{getattr(Fore, COLORS_16[base])}{text}{Style.RESET_ALL}"
        else:
            return text

    if r is not None and g is not None and b is not None:
        if CAPS["color_depth"] == "truecolor":
            return f"\033[38;2;{r};{g};{b}m{text}\033[0m"
        elif CAPS["color_depth"] in ("256", "16"):
            ansi_256 = rgb_to_256(r, g, b)
            if CAPS["color_depth"] == "256":
                return f"\033[38;5;{ansi_256}m{text}\033[0m"
            else:
                color_name = map_256_to_16(ansi_256)
                return f"{getattr(Fore, color_name)}{text}{Style.RESET_ALL}"
        else:
            return text
    return text

def rgb_to_256(r, g, b):
    if r == g == b:
        if r < 8: return 16
        if r > 248: return 231
        return int(232 + (r - 8) / 10)
    r6 = int(r / 51)
    g6 = int(g / 51)
    b6 = int(b / 51)
    return 16 + 36 * r6 + 6 * g6 + b6

COLORS_16 = {
    0: 'BLACK', 1: 'RED', 2: 'GREEN', 3: 'YELLOW',
    4: 'BLUE', 5: 'MAGENTA', 6: 'CYAN', 7: 'WHITE',
    8: 'BLACK', 9: 'RED', 10: 'GREEN', 11: 'YELLOW',
    12: 'BLUE', 13: 'MAGENTA', 14: 'CYAN', 15: 'WHITE'
}
def map_256_to_16(code):
    if code < 16:
        return COLORS_16[code]
    if code >= 232:
        return "WHITE" if code > 244 else "BLACK"

    code -= 16
    r = code // 36
    g = (code % 36) // 6
    b = code % 6

    intensity = (r + g + b) / 3
    if intensity > 4: return "WHITE"
    if intensity > 2: return "GREEN" if g > r and g > b else "YELLOW" if r > 2 and g > 2 else "CYAN" if g > 2 and b > 2 else "MAGENTA" if r > 2 and b > 2 else "RED" if r > 3 else "BLUE"
    return "BLACK"


def clear_screen():
    if CAPS["ansi"]:
        sys.stdout.write("\033[2J\033[H")
    else:
        sys.stdout.write("\n" * 100)
    sys.stdout.flush()

def hide_cursor():
    if CAPS["ansi"]:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

def show_cursor():
    if CAPS["ansi"]:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def move_up(lines=1):
    if CAPS["ansi"]:
        sys.stdout.write(f"\033[{lines}A")
        sys.stdout.flush()

# ---------- ascll ----------
LOGO_UNICODE = [
    (196, "██╗    ██╗       ██████╗       ██████╗      ██╗         ██╗"),
    (202, "██║    ██║     ██╔═══██╗     ██╔════╝      ██║         ██║"),
    (208, "██║ █╗ ██║     ██║   ██║     ██║           ██║         ██║"),
    (214, "██║███╗██║     ██║   ██║     ██║           ██║         ██║"),
    (220, "╚███╔███╔╝     ╚██████╔╝     ╚██████╗      ███████╗    ██║"),
    (226, " ╚══╝╚══╝       ╚═════╝       ╚═════╝      ╚══════╝    ╚═╝"),
]

LOGO_ASCII = [
    (1, " __      __   ___    ___   _       ___ "),
    (2, " \\ \\    / /  / _ \\  / __| | |     |_ _|"),
    (3, "  \\ \\/\\/ /  | (_) | | (__  | |__    | | "),
    (4, "   \\_/\\_/    \\___/   \\___| |____|  |___|"),
]

def get_logo():
    if CAPS["unicode"] and CAPS["color_depth"] in ("truecolor", "256"):
        lines = []
        for ansi_code, line in LOGO_UNICODE:
            colored_line = "".join(
                colored(ch, ansi_code=ansi_code) if ch.strip() else ch
                for ch in line
            )
            lines.append(colored_line)
        return "\n".join(lines)
    elif CAPS["color_depth"] == "16":
        lines = []
        for ansi_code, line in LOGO_ASCII:
            color_name = map_256_to_16(ansi_code)
            colored_line = f"{getattr(Fore, color_name)}{line}{Style.RESET_ALL}"
            lines.append(colored_line)
        return "\n".join(lines)
    else:

        return "\n".join([line for _, line in LOGO_ASCII])

# 在 import 本模块时并不执行，需要主动调用 init_terminal