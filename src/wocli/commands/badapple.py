"""wocli badapple - 播放 Bad Apple!! ASCII 动画"""
import sys
import os
import time

C_WHITE = "\033[97m"
C_RESET = "\033[0m"

FRAME_FILE = os.path.join(os.path.dirname(__file__), "frames.txt")


def load_frames():
    """加载帧序列，返回帧列表"""
    if not os.path.exists(FRAME_FILE):
        print("\n  frames.txt 未找到，请确保下载了 Bad Apple ASCII 帧序列并放到 commands/ 目录。")
        print("  下载地址: https://raw.githubusercontent.com/kevinjycui/bad-apple/main/frames.txt\n")
        return None
    with open(FRAME_FILE, "r", encoding="utf-8") as f:
        data = f.read()
    # 帧之间用 SPLIT 分隔，每一帧是一段文本
    frames = data.split("\nSPLIT\n")
    return frames


def run():
    print("\n  [ Bad Apple!! ]")
    print("  正在加载帧序列...")
    frames = load_frames()
    if not frames:
        return
    print(f"  共 {len(frames)} 帧，按 Enter 开始播放...")
    input()

    # 隐藏光标
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        for frame in frames:
            # 将光标移到终端左上角（不清屏，直接覆盖）
            sys.stdout.write("\033[H")
            sys.stdout.write(C_WHITE + frame + C_RESET)
            sys.stdout.flush()
            time.sleep(1 / 30)   # 30fps，可根据机器性能调整
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")  # 恢复光标
        sys.stdout.write(C_RESET)
        sys.stdout.flush()
        print("\n  播放完毕。")