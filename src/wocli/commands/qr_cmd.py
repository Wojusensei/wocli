"""wocli qr - 终端生成可扫码的二维码."""

import sys
import qrcode

from wocli import terminal


def run():
    """运行 qr 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli qr <文字或链接>\n")
        return

    text = " ".join(sys.argv[1:])

    # 生成二维码矩阵
    qr = qrcode.QRCode(
        version=None,
        # M 级纠错（15%）：手机拍屏幕有摩尔纹和终端行间隙条纹，L 级扛不住
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        # 静区必须 >=4 模块（QR 标准 ISO/IEC 18004），不足会被微信等
        # 严格解码器直接判为无法识别
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    modules = qr.modules

    print()
    print(f"  [ QR Code: {text[:40]}{'...' if len(text) > 40 else ''} ]")
    print()

    # Unicode 半块字符逐行渲染，两个模块拼进一个字符。
    # 颜色不能依赖终端主题：深色背景下会输出反色码，多数扫码器不认。
    # 用 ANSI 固定"白底黑块"（黑前景画半块，白背景当浅色模块），
    # 不支持 ANSI 的终端退回默认配色
    if terminal.CAPS.get("ansi"):
        color_on, color_off = "\033[30;107m", "\033[0m"
    else:
        color_on = color_off = ""

    for y in range(0, len(modules), 2):
        line = "  " + color_on
        for x in range(len(modules[0])):
            upper = modules[y][x]
            lower = modules[y + 1][x] if y + 1 < len(modules) else False

            if upper and lower:
                line += "\u2588"
            elif upper:
                line += "\u2580"
            elif lower:
                line += "\u2584"
            else:
                line += " "
        print(line + color_off)

    print()
    print(f"  扫描上方二维码查看内容")
    print(f"  （扫不出时：调大终端字号或换等宽字体，块字符需填满行高）")
    print()