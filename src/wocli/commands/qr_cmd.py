"""wocli qr - 终端生成可扫码的二维码.

渲染方式参照 libqrencode 的成熟实现：
  - `-t ANSI`    一个模块两个字符宽、只用背景色（本文件的 render_wide，默认）
  - `-t ANSIUTF8` 一个字符装上下两个模块、靠半块字形（render_compact，窄终端用）
两者都带 ISO/IEC 18004 要求的 4 模块静区，极性都是"深色模块看起来是深色"。
"""

import shutil
import sys

import qrcode

from wocli import terminal

INDENT = "  "
RESET = "\033[0m"
QUIET_ZONE = 4                    # 静区宽度（模块数），ISO/IEC 18004 要求 >= 4
WHITE_BG = "\033[47m"             # 浅色模块：白底
BLACK_BG = "\033[40m"             # 深色模块：黑底
BLACK_ON_WHITE = "\033[40;37;1m"  # 紧凑模式：黑底 + 亮白前景（同 qrencode ANSIUTF8）
OVERHEAD_LINES = 8                # 标题、说明、提示大概占掉的行数

FULL = "\u2588"
UPPER_HALF = "\u2580"
LOWER_HALF = "\u2584"
EMPTY = " "


def add_quiet_zone(matrix, size=QUIET_ZONE):
    """在符号四周补浅色静区.

    qrcode 的 `border` 参数只对 make_image() 生成的图片生效，`qr.modules`
    是不含静区的符号本体。终端渲染以前直接用 modules，等于把定位图形画在
    边上，缺了标准要求的 4 模块空白——严格些的解码器会判为无法识别。
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


def choose_layout(module_count, columns):
    """优先宽渲染；宽度不够才退回紧凑渲染."""
    if module_count * 2 + len(INDENT) <= columns:
        return "wide"
    return "compact"


def render_wide(matrix):
    """宽渲染：一个模块两个字符宽、只靠背景色（qrencode -t ANSI）.

    完全不依赖字体字形：字符宽度、行高、字体回退都不影响它；
    2 字符宽 x 1 行高在常见 1:2 的字符格里正好是正方形模块。
    """
    lines = []
    for row in matrix:
        parts = [WHITE_BG]
        current = False
        for dark in row:
            dark = bool(dark)
            if dark != current:
                parts.append(BLACK_BG if dark else WHITE_BG)
                current = dark
            parts.append("  ")
        parts.append(RESET)
        lines.append(INDENT + "".join(parts))
    return lines


def render_compact(matrix):
    """紧凑渲染：一个字符装上下两个模块（qrencode -t ANSIUTF8）.

    浅色模块用亮白前景画成方块、深色模块留黑底，极性正确：
    深色模块看起来是深色，浅色模块看起来是白色。
    """
    lines = []
    blank = [False] * len(matrix[0])
    for y in range(0, len(matrix), 2):
        lower = matrix[y + 1] if y + 1 < len(matrix) else blank
        chars = []
        for upper_dark, lower_dark in zip(matrix[y], lower):
            if upper_dark and lower_dark:
                chars.append(EMPTY)          # 两个都深：留黑底
            elif upper_dark:
                chars.append(LOWER_HALF)     # 上深下浅：下半块白
            elif lower_dark:
                chars.append(UPPER_HALF)     # 上浅下深：上半块白
            else:
                chars.append(FULL)           # 两个都浅：整块白
        lines.append(INDENT + BLACK_ON_WHITE + "".join(chars) + RESET)
    return lines


def render_plain(matrix):
    """不支持 ANSI 时的兜底：同样的半块字形，靠终端默认配色."""
    lines = []
    blank = [False] * len(matrix[0])
    for y in range(0, len(matrix), 2):
        lower = matrix[y + 1] if y + 1 < len(matrix) else blank
        chars = []
        for upper_dark, lower_dark in zip(matrix[y], lower):
            if upper_dark and lower_dark:
                chars.append(EMPTY)
            elif upper_dark:
                chars.append(LOWER_HALF)
            elif lower_dark:
                chars.append(UPPER_HALF)
            else:
                chars.append(FULL)
        lines.append(INDENT + "".join(chars))
    return lines


def render_svg(matrix, path):
    """把二维码写成 SVG 文件，完全不依赖终端——字体、行距、窗口大小都影响不到它."""
    size = len(matrix)
    rects = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
    # 每个模块 8x8 像素；crispEdges 关掉抗锯齿，避免模块之间出现灰边
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{size * 8}" height="{size * 8}" '
        'shape-rendering="crispEdges">\n'
        f'<rect width="{size}" height="{size}" fill="#ffffff"/>\n'
        '<g fill="#000000">\n'
        + "\n".join(rects)
        + "\n</g>\n</svg>\n"
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(svg)


def parse_args(argv=None):
    """解析参数：wocli qr [--svg 文件] [--compact] <文字或链接>."""
    args = list(sys.argv[1:] if argv is None else argv)
    svg_path = None
    compact = False
    rest = []
    index = 0
    while index < len(args):
        item = args[index]
        if item in ("--svg", "-s") and index + 1 < len(args):
            svg_path = args[index + 1]
            index += 2
        elif item in ("--compact", "-c"):
            compact = True
            index += 1
        else:
            rest.append(item)
            index += 1
    return " ".join(rest), svg_path, compact


def run():
    """运行 qr 命令."""
    text, svg_path, compact = parse_args()
    if not text:
        print("\n  用法: wocli qr <文字或链接>")
        print("        导出图片：wocli qr --svg 文件名.svg <文字或链接>")
        print("        强制紧凑渲染：wocli qr --compact <文字或链接>\n")
        return

    matrix = build_matrix(text)
    module_count = len(matrix[0])
    term = shutil.get_terminal_size((80, 24))
    use_ansi = bool(terminal.CAPS.get("ansi"))

    if not use_ansi:
        layout = "plain"
    elif compact:
        layout = "compact"
    else:
        layout = choose_layout(module_count, term.columns)

    if layout == "wide":
        lines = render_wide(matrix)
        width = module_count * 2 + len(INDENT)
    elif layout == "compact":
        lines = render_compact(matrix)
        width = module_count + len(INDENT)
    else:
        lines = render_plain(matrix)
        width = module_count + len(INDENT)

    print()
    print(f"  [ QR Code: {text[:40]}{'...' if len(text) > 40 else ''} ]")
    if layout == "compact" and not compact:
        wide_width = module_count * 2 + len(INDENT)
        print(f"  （终端只有 {term.columns} 列，宽渲染要 {wide_width} 列，已改用紧凑渲染）")
    # 显示不下的提示放在二维码前面：万一行数超过窗口、二维码把屏幕顶滚走，提示还在
    if width > term.columns:
        print(f"  提示：这枚二维码要占 {width} 列，当前终端只有 {term.columns} 列，"
              f"换行会扫不出来")
        print("  建议：放大窗口，或用 wocli qr --svg 文件名.svg 导出成图片再扫")
    elif len(lines) + OVERHEAD_LINES > term.lines:
        print(f"  提示：二维码有 {len(lines)} 行，当前窗口只有 {term.lines} 行，"
              f"可能显示不全")
        print("  建议：最大化窗口，或用 wocli qr --svg 文件名.svg 导出成图片再扫")
    print()
    for line in lines:
        print(line)
    print()
    print("  扫描上方二维码查看内容")

    if svg_path:
        render_svg(matrix, svg_path)
        print(f"  已保存 SVG：{svg_path}（用浏览器或预览打开，对着屏幕扫）")
    if not use_ansi:
        print("  （当前终端不支持 ANSI 颜色，二维码可能不够清晰，建议用 --svg 导出）")
    print()
