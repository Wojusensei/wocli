"""wocli badapple - 播放 Bad Apple!! ASCII 动画"""
import sys
import os
import time

C_WHITE = "\033[97m"
C_RESET = "\033[0m"

FRAME_FILE = os.path.join(os.path.dirname(__file__), "frames.txt")

DOWNLOAD_URL = "https://raw.githubusercontent.com/kevinjycui/bad-apple/main/frames.txt"


def load_frames(frame_file=None):
    """加载帧序列，返回帧列表。

    帧文件查找顺序：命令行参数 > 环境变量 WOCLI_BADAPPLE_FRAMES > 模块目录下的 frames.txt
    """
    candidates = [
        frame_file,
        os.environ.get("WOCLI_BADAPPLE_FRAMES"),
        FRAME_FILE,
    ]
    path = next((p for p in candidates if p and os.path.exists(p)), None)

    if path is None:
        print("\n  未找到 Bad Apple 帧序列文件。")
        print("  下载地址: " + DOWNLOAD_URL)
        print("  下载后可通过以下任意方式使用：")
        print("    wocli badapple /path/to/frames.txt")
        print("    export WOCLI_BADAPPLE_FRAMES=/path/to/frames.txt\n")
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    # 帧之间用 SPLIT 分隔，每一帧是一段文本
    frames = data.split("\nSPLIT\n")
    return frames


def run():
    print("\n  [ Bad Apple!! ]")
    print("  正在加载帧序列...")
    frames = load_frames(sys.argv[1] if len(sys.argv) > 1 else None)
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