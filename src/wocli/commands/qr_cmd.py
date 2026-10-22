"""wocli qr - 终端生成可扫码的二维码."""

import shutil
import sys

import qrcode

from wocli import terminal

INDENT = "  "
RESET = "\033[0m"
QUIET_ZONE = 4  # 静区宽度（模块数），ISO/IEC 18004 要求 >= 4
OVERHEAD_LINES = 6  # 标题和说明占掉的终端行数，用来判断整枚二维码能否一屏放下

# 浅色模块用亮白、深色模块用黑
_FG = {False: 97, True: 30}
_BG = {False: 107, True: 40}
_HALF_BLOCK = "\u2580"


def add_quiet_zone(matrix, size=QUIET_ZONE):
    """在符号四周补浅色静区.

    qrcode 的 `border` 参数只对 make_image() 生成的图片生效，`qr.modules`
    是不含静区的符号本体。终端渲染以前直接用 modules，等于把定位图形画在
    边上，缺了标准要求的 4 模块空白，微信这类严格解码器会直接判为无法识别。
    """
    width = len(matrix[0]) + size * 2
    blank = [False] * width
    padded = [list(blank) for _ in range(size)]
    for row in matrix:
        padded.append([False] * size + list(row) + [False] * size)
    padded.extend(list(blank) for _ in range(size))
    return padded


def build_matrix(text):
    """生成带静区的模块矩阵."""
    qr = qrcode.QRCode(
        version=None,
        # M 级纠错（15%）：手机拍屏幕有摩尔纹和终端行缝隙，L 级扛不住
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=QUIET_ZONE,
    )
    qr.add_data(text)
    qr.make(fit=True)
    return add_quiet_zone(qr.modules, QUIET_ZONE)


def choose_layout(module_count, columns, lines):
    """按终端尺寸挑渲染方式.

    "cells"：一个模块一个字符格、只靠背景色，完全不依赖字体字形；代价是
    每行只装一个模块，v2 的二维码就要 33 行。
    "blocks"：上下两个模块拼一个字符，只用一半行数，但依赖字体把 ▀ 画满半格，
    而且字符格不是 1:2 时模块会被压扁，所以只在窗口放不下时使用。
    """
    if module_count + OVERHEAD_LINES > lines:
        return "blocks", 1
    if module_count * 2 + len(INDENT) <= columns:
        return "cells", 2
    if module_count + len(INDENT) <= columns:
        return "cells", 1
    return "blocks", 1


def _codes(upper, lower):
    return "\033[%d;%dm" % (_FG[bool(upper)], _BG[bool(lower)])


def render_blocks(matrix):
    """半块渲染：一个字符装上下两个模块，前景画上半、背景当下半.

    上下模块同色时前景=背景，整格同色，字形边缘的微小缝隙会被同色背景兜住；
    以前固定"白底 + 黑前景"，缝隙会露出白色，把深色模块切成横条（实测 Menlo
    下旧画法全部解码失败，这种画法全部成功）。
    """
    lines = []
    blank = [False] * len(matrix[0])
    for y in range(0, len(matrix), 2):
        upper = matrix[y]
        lower = matrix[y + 1] if y + 1 < len(matrix) else blank
        parts = []
        last = None
        for up, low in zip(upper, lower):
            pair = (bool(up), bool(low))
            if pair != last:
                parts.append(_codes(up, low))
                last = pair
            parts.append(_HALF_BLOCK)
        parts.append(RESET)
        lines.append(INDENT + "".join(parts))
    return lines


def render_cells(matrix, scale=1):
    """整格渲染：一行一个模块，只靠背景色，和字体长什么样无关."""
    lines = []
    for row in matrix:
        parts = []
        last = None
        for dark in row:
            dark = bool(dark)
            if dark != last:
                parts.append("\033[%dm" % _BG[dark])
                last = dark
            parts.append(" " * scale)
        parts.append(RESET)
        lines.append(INDENT + "".join(parts))
    return lines


def render_plain(matrix):
    """不支持 ANSI 时的兜底：用 █▀▄ 半块字符，靠终端默认前景色显示."""
    lines = []
    blank = [False] * len(matrix[0])
    for y in range(0, len(matrix), 2):
        upper = matrix[y]
        lower = matrix[y + 1] if y + 1 < len(matrix) else blank
        chars = []
        for up, low in zip(upper, lower):
            if up and low:
                chars.append("\u2588")
            elif up:
                chars.append("\u2580")
            elif low:
                chars.append("\u2584")
            else:
                chars.append(" ")
        lines.append(INDENT + "".join(chars))
    return lines


def run():
    """运行 qr 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli qr <文字或链接>\n")
        return

    text = " ".join(sys.argv[1:])
    matrix = build_matrix(text)
    module_count = len(matrix[0])
    term = shutil.get_terminal_size((80, 24))

    print()
    print(f"  [ QR Code: {text[:40]}{'...' if len(text) > 40 else ''} ]")
    print()

    if terminal.CAPS.get("ansi"):
        mode, scale = choose_layout(module_count, term.columns, term.lines)
        if mode == "cells":
            lines = render_cells(matrix, scale)
        else:
            lines = render_blocks(matrix)
    else:
        lines = render_plain(matrix)
    for line in lines:
        print(line)

    print()
    print("  扫描上方二维码查看内容")
    if module_count + len(INDENT) > term.columns:
        print(f"  提示：这枚二维码要占 {module_count + len(INDENT)} 列，"
              f"当前终端只有 {term.columns} 列，换行会扫不出来")
        print("  建议放大窗口或缩短内容")
    if not terminal.CAPS.get("ansi"):
        print("  （当前终端不支持 ANSI 颜色，二维码可能不够清晰）")
    print()
