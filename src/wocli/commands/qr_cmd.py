"""wocli qr - 终端生成可扫码的二维码."""

import sys
import qrcode


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
    print(f"  （扫不出时：调大终端字号或换等宽字体，块字符需填满行高）")
    print()