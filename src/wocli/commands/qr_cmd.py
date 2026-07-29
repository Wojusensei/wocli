"""wocli qr - 终端生成可扫码的二维码."""

import sys
import qrcode
from qrcode.image.pil import PilImage


def run():
    """运行 qr 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli qr <文字或链接>\n")
        return

    text = " ".join(sys.argv[1:])

    # 生成二维码矩阵
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=1,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    modules = qr.modules

    print()
    print(f"  [ QR Code: {text[:40]}{'...' if len(text) > 40 else ''} ]")
    print()

    # Unicode 
    for y in range(0, len(modules), 2):
        line = "  "
        for x in range(len(modules[0])):
            upper = modules[y][x] if y < len(modules) else False
            lower = modules[y + 1][x] if y + 1 < len(modules) else False

            if upper and lower:
                line += "\u2588"  
            elif upper and not lower:
                line += "\u2580"  
            elif not upper and lower:
                line += "\u2584"  
            else:
                line += " "
        print(line)

    print()
    print(f"  扫描上方二维码查看内容")
    print()