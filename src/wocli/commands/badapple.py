"""wocli badapple - 播放 Bad Apple!! ASCII 动画（可选配乐）

帧序列共 6572 帧（100x75，多级 ASCII 灰度字符），来自
TryCaze/Bad-Apple-ASCII。首次使用自动下载 zip（约 4.6MB）并解包为
gzip 缓存，之后离线播放；灰度字符统一渲染为 ░▒▓█ 块字符。
可选下载配套 mp3（约 5.6MB），用系统播放器（afplay/ffplay/mpv）同步播放。
帧源查找顺序：命令行路径 > 环境变量 WOCLI_BADAPPLE_FRAMES > 模块目录
frames.txt > 本地缓存 > 自动下载生成缓存。
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
from itertools import groupby

from wocli import terminal

C_RESET = "\033[0m"
FPS = 30
FRAME_W, FRAME_H = 100, 75
FRAME_FILE = os.path.join(os.path.dirname(__file__), "frames.txt")
ZIP_URL = "https://raw.githubusercontent.com/TryCaze/Bad-Apple-ASCII/main/ASCIIframes.zip"
MUSIC_URL = "https://raw.githubusercontent.com/TryCaze/Bad-Apple-ASCII/main/music/badapple.mp3"

# 帧源是 ASCII 灰度字符（亮->暗大致为 : - + = * # % @），映射成块字符
CHAR_MAP = str.maketrans({
    "@": "█", "%": "▓", "#": "▓",
    "*": "▒", "=": "▒", "+": "▒",
    "-": "░", ":": "░",
})

# 块字符 ░▒▓█ 是 Unicode 宽度模糊字符，中文环境下不少终端渲染成两列宽，
# 一行 100 字符折成 200 列造成画面上下错位抖动；空格在任何终端都是一列，
# 因此默认用"背景色画空格"渲染，块字符仅作无色终端的降级方案

# 原帧 9 级 ASCII 灰度映射到 256 色。色档与仓库 v0.5.0 版本完全一致
# （8 级灰度并成 4 档 + 背景近黑），仅渲染载体从块字符换成背景色空格
GRAY_BG = {
    "@": "231", "%": "250", "#": "250",
    "*": "244", "=": "244", "+": "244",
    "-": "238", ":": "238", " ": "233",
}


def render_bg_lines(frame):
    """把原始灰度帧转成行程编码的背景色空格行列表（列宽恒为一格）。"""
    lines = []
    for line in frame.split("\n"):
        parts = []
        for ch, grp in groupby(line):
            n = sum(1 for _ in grp)
            parts.append(f"\033[48;5;{GRAY_BG.get(ch, '232')}m{' ' * n}")
        parts.append("\033[49m")
        lines.append("".join(parts))
    return lines


def _cache_dir():
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return os.path.join(base, "wocli")


def _cache_path():
    return os.path.join(_cache_dir(), "badapple_frames.txt.gz")


def _music_cache_path():
    return os.path.join(_cache_dir(), "badapple_music.mp3")


def _download_to(url, dest):
    """优先 urllib；证书验证失败（常见于 Watt Toolkit 等加速器替换了证书）
    时退回系统 curl——同样严格校验 TLS，只是用系统信任库。"""
    req = urllib.request.Request(url, headers={"User-Agent": "wocli"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        sys.stdout.write(f"\r  下载中... {done * 100 // total}% ({done // 1024}KB)")
                        sys.stdout.flush()
        print()
        return
    except Exception as e:
        curl = shutil.which("curl")
        if not curl:
            raise
        print(f"  直接下载失败（{e}），改用系统 curl 重试...")
    subprocess.run([curl, "-fsSL", "--max-time", "600", "-o", dest, url], check=True)
    print(f"  下载完成（{os.path.getsize(dest) // 1024}KB）")


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


def _fetch_and_cache():
    """下载 zip，逐帧解包写入 gzip 缓存，返回帧列表."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tf:
        tmp = tf.name
    try:
        _download_to(ZIP_URL, tmp)
        with open(tmp, "rb") as f:
            data = f.read()
    finally:
        os.unlink(tmp)

    frames = []
    cache = _cache_path()
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    # 帧内容全是 ASCII 灰度字符，level 1 也压得很好且快得多
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


# ---------- 配乐 ----------

# Windows 无内置命令行 mp3 播放器，用系统自带 WMP 的 COM 接口兜底
# （WMP 异步播放，进程需存活到播放结束，playState 1 = Stopped）
_WMP_PS = (
    "$ErrorActionPreference='Stop';"
    "$p = New-Object -ComObject WMPlayer.OCX.7;"
    "$p.URL = '{path}';"
    "$p.controls.play();"
    "while ($p.playState -ne 1) { Start-Sleep -Milliseconds 300 }"
)


def _start_music(music_path):
    """用系统可用的播放器启动音乐，返回 Popen；找不到可用方式返回 None。"""
    for name, args in (
        ("afplay", ["afplay"]),                                        # macOS 自带
        ("ffplay", ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]),
        ("mpv", ["mpv", "--no-video", "--really-quiet"]),
    ):
        if shutil.which(name):
            try:
                return subprocess.Popen(
                    args + [music_path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except OSError:
                return None
    if platform.system() == "Windows" and shutil.which("powershell"):
        script = _WMP_PS.replace("{path}", music_path.replace("'", "''"))
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            return None
        # WMP COM 创建失败时 powershell 会立即退出（如精简版系统移除了 WMP）
        time.sleep(1.0)
        if proc.poll() is None:
            return proc
        return None
    return None


def _maybe_get_music():
    """返回音乐缓存路径；不可用/未下载时返回 None。"""
    path = _music_cache_path()
    if not os.path.exists(path):
        print("  有配套背景音乐可下载（约 5.6MB），播放动画时自动配乐。")
        try:
            ans = input("  现在下载？[Y/n]：").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  跳过音乐。")
            return None
        if ans in ("n", "no"):
            return None
        os.makedirs(_cache_dir(), exist_ok=True)
        try:
            _download_to(MUSIC_URL, path)
        except Exception as e:
            print(f"  音乐下载失败（{e}），将无声播放。")
            try:
                os.unlink(path)
            except OSError:
                pass
            return None
    if shutil.which("afplay") or shutil.which("ffplay") or shutil.which("mpv"):
        return path
    if platform.system() == "Windows" and shutil.which("powershell"):
        return path  # 走 WMP COM 兜底
    print("  未找到音频播放器（afplay/ffplay/mpv），将无声播放。")
    if platform.system() == "Windows":
        print("  提示：安装 ffmpeg 后可自动配乐：winget install Gyan.FFmpeg")
    elif platform.system() == "Linux":
        print("  提示：安装 ffmpeg 或 mpv 后可自动配乐，例如：sudo apt install ffmpeg")
    return None


def run():
    print("\n  [ Bad Apple!! ]")
    frames = load_frames(sys.argv[1] if len(sys.argv) > 1 else None)
    if not frames:
        return
    try:
        fps = int(os.environ.get("WOCLI_BADAPPLE_FPS", "30") or 30)
    except ValueError:
        fps = 30
    fps = max(1, min(60, fps))
    print(f"  共 {len(frames)} 帧，约 {len(frames) / fps:.0f} 秒 @ {fps}fps")

    player, music_path = None, _maybe_get_music()

    try:
        cols, lines = os.get_terminal_size()
        # 个别非交互环境返回 0x0，视为无法检测；要求比帧高多一行余量，
        # 光标停在终端最后一行行尾时部分终端会先滚动再执行光标定位
        if 0 < cols < FRAME_W or 0 < lines < FRAME_H + 1:
            print(f"  当前终端 {cols}x{lines}，建议至少 {FRAME_W}x{FRAME_H + 1}，否则画面会滚动错位")
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

    # 渲染模式：默认背景色画空格（列宽恒定，杜绝宽字符折行抖动）；
    # 无色终端降级为块字符；WOCLI_BADAPPLE_BG=1/0 可强制指定
    use_bg = os.environ.get("WOCLI_BADAPPLE_BG")
    if use_bg is None:
        use_bg = "1" if terminal.CAPS.get("color_depth") in ("truecolor", "256") else "0"
    if use_bg == "0":
        print("  使用块字符渲染（当前终端不支持 256 色，部分环境下可能错位）")

    rewind = f"\033[K\033[{FRAME_H - 1}A\r"
    # 预渲染：加载期把全部帧编码为 bytes，播放循环只剩内存写入，
    # 把 CPU 尽量让给终端渲染和音频解码，减少更新节奏抖动
    print("  正在准备画面...", end="", flush=True)
    bg_mode = use_bg == "1"
    rendered = []
    for frame in frames:
        body = "\n".join(render_bg_lines(frame)) if bg_mode else frame.translate(CHAR_MAP)
        rendered.append(("\033[H" + body + rewind).encode("utf-8"))
    frames = rendered
    print(" 完成")

    music_proc = None
    if music_path:
        music_proc = _start_music(music_path)
        if music_proc is None:
            print("  音频播放器启动失败，继续无声播放。")

    # 进入备用屏幕缓冲区（vim/htop 同款）：Terminal.app 等纯 CPU 渲染的
    # 终端在备用屏下处理路径更干净，且动画不会污染正常会话的滚动缓冲
    sys.stdout.write("\033[?1049h\033[?25l")
    sys.stdout.flush()
    frame_time = 1 / fps
    start = time.monotonic()
    interrupted = False
    out_write = sys.stdout.buffer.write
    try:
        for i, frame in enumerate(frames):
            out_write(frame)
            sys.stdout.buffer.flush()
            # 按时间轴对齐，渲染耗时不会累积拖慢整曲
            target = start + (i + 1) * frame_time
            time.sleep(max(0.0, target - time.monotonic()))
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if music_proc is not None:
            # 播放器无需优雅退出，SIGTERM 对部分播放器无效，直接 SIGKILL
            music_proc.kill()
            try:
                music_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        sys.stdout.write(C_RESET + "\033[?25h\033[?1049l")
        sys.stdout.flush()
        print("  已中断。" if interrupted else "  播放完毕。")
