"""wocli badapple - 播放 Bad Apple!! ASCII 动画

帧序列共 6572 帧（100x74，'@' 为暗像素），来自 TryCaze/Bad-Apple-ASCII。
首次使用自动下载 zip（约 4.6MB）并解包为 gzip 缓存，之后离线播放。
查找顺序：命令行路径 > 环境变量 WOCLI_BADAPPLE_FRAMES > 模块目录 frames.txt
> 本地缓存 > 自动下载生成缓存。
"""
import gzip
import io
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

C_RESET = "\033[0m"
FPS = 30
FRAME_W, FRAME_H = 100, 75
FRAME_FILE = os.path.join(os.path.dirname(__file__), "frames.txt")
ZIP_URL = "https://raw.githubusercontent.com/TryCaze/Bad-Apple-ASCII/main/ASCIIframes.zip"


def _cache_path():
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "wocli", "badapple_frames.txt.gz")


def _read_frames(path):
    if os.path.isdir(path):
        frames = []
        for name in sorted(os.listdir(path)):
            if name.endswith(".txt"):
                with open(os.path.join(path, name), encoding="utf-8") as f:
                    frames.append(f.read().strip())
        return frames
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = f.read()
    else:
        with open(path, encoding="utf-8") as f:
            data = f.read()
    return data.split("\nSPLIT\n")


def _download_zip():
    """优先 urllib；证书验证失败（常见于 Watt Toolkit 等加速器替换了证书）
    时退回系统 curl——同样严格校验 TLS，只是用系统信任库。"""
    req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "wocli"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            buf = io.BytesIO()
            done = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                buf.write(chunk)
                done += len(chunk)
                if total:
                    sys.stdout.write(f"\r  下载中... {done * 100 // total}% ({done // 1024}KB)")
                    sys.stdout.flush()
        print()
        return buf.getvalue()
    except Exception as e:
        curl = shutil.which("curl")
        if not curl:
            raise
        print(f"  直接下载失败（{e}），改用系统 curl 重试...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tf:
            tmp = tf.name
        try:
            subprocess.run([curl, "-fsSL", "--max-time", "600", "-o", tmp, ZIP_URL], check=True)
            with open(tmp, "rb") as f:
                data = f.read()
            print(f"  下载完成（{len(data) // 1024}KB）")
            return data
        finally:
            os.unlink(tmp)


def _fetch_and_cache():
    """下载 zip，逐帧解包写入 gzip 缓存，返回帧列表."""
    data = _download_zip()

    frames = []
    cache = _cache_path()
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    # 帧内容全是 '@' 和空格，level 1 也压得很好且快得多
    with zipfile.ZipFile(io.BytesIO(data)) as z, gzip.open(cache, "wt", encoding="utf-8", compresslevel=1) as out:
        names = sorted(n for n in z.namelist() if n.endswith(".txt"))
        for i, name in enumerate(names):
            frame = z.read(name).decode("utf-8", "replace").strip()
            frames.append(frame)
            if i:
                out.write("\nSPLIT\n")
            out.write(frame)
    print(f"  已缓存到 {cache}")
    return frames


def load_frames(frame_file=None):
    """加载帧序列，找不到时提示下载."""
    candidates = [
        frame_file,
        os.environ.get("WOCLI_BADAPPLE_FRAMES"),
        FRAME_FILE,
        _cache_path(),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return _read_frames(path)

    print("  本地没有帧序列，首次使用需要联网下载（约 4.6MB，之后缓存离线播放）。")
    try:
        input("  回车开始下载，Ctrl+C 取消...")
    except (EOFError, KeyboardInterrupt):
        print("\n  已取消。\n")
        return None
    try:
        return _fetch_and_cache()
    except Exception as e:
        print(f"\n  下载失败：{e}")
        print(f"  可手动获取 {ZIP_URL} 解压后运行：wocli badapple <帧目录>\n")
        return None


def run():
    print("\n  [ Bad Apple!! ]")
    frames = load_frames(sys.argv[1] if len(sys.argv) > 1 else None)
    if not frames:
        return
    print(f"  共 {len(frames)} 帧，约 {len(frames) / FPS:.0f} 秒 @ {FPS}fps")

    try:
        cols, lines = os.get_terminal_size()
        if cols < FRAME_W or lines < FRAME_H:
            print(f"  当前终端 {cols}x{lines}，建议至少 {FRAME_W}x{FRAME_H}，否则画面会滚动错位")
            try:
                input("  回车继续，Ctrl+C 取消...")
            except (EOFError, KeyboardInterrupt):
                print("\n  已取消。\n")
                return
    except OSError:
        pass

    print("  按 Enter 开始播放...", end="", flush=True)
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("\n  已取消。\n")
        return

    sys.stdout.write("\033[?25l\033[2J")
    sys.stdout.flush()
    frame_time = 1 / FPS
    start = time.monotonic()
    interrupted = False
    try:
        for i, frame in enumerate(frames):
            # '@' 是暗像素，换成实心块播放（自备帧里若已是块字符则原样保留）
            sys.stdout.write("\033[H" + frame.replace("@", "█"))
            sys.stdout.flush()
            # 按时间轴对齐，渲染耗时不会累积拖慢整曲
            target = start + (i + 1) * frame_time
            time.sleep(max(0.0, target - time.monotonic()))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        sys.stdout.write(C_RESET + "\033[?25h\n")
        sys.stdout.flush()
        print("  已中断。" if interrupted else "  播放完毕。")
