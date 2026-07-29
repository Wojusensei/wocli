"""wocli time - 测试代码运行耗时."""

import subprocess
import time
import sys
import os
import platform


def run():
    """运行 time 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli time <文件路径>\n")
        return

    filepath = sys.argv[1]

    if not os.path.isfile(filepath):
        print(f"\n  文件不存在: {filepath}\n")
        return

    filename = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    # 根据扩展名选择执行方式
    commands = {
        ".py": ["python3", filepath],
        ".pyw": ["python3", filepath],
        ".js": ["node", filepath],
        ".sh": ["bash", filepath],
        ".bash": ["bash", filepath],
        ".zsh": ["zsh", filepath],
        ".rb": ["ruby", filepath],
        ".pl": ["perl", filepath],
        ".lua": ["lua", filepath],
    }

    if ext in commands:
        cmd = commands[ext]
    elif platform.system() == "Windows" and ext in (".exe", ".bat", ".cmd"):
        cmd = [filepath]
    elif os.access(filepath, os.X_OK):
        cmd = [filepath]
    else:
        print(f"\n  不支持的文件类型: {ext}\n")
        return

    print()
    print(f"  [ 代码耗时测试 ]")
    print(f"  文件: {filename}")
    print(f"  正在运行...")

    try:
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        elapsed = time.perf_counter() - start

        print(f"  " + "-" * 30)
        print(f"  耗时: {elapsed:.3f} 秒")

        if result.returncode == 0:
            print(f"  状态: 运行成功")
        else:
            print(f"  状态: 运行失败 (退出码 {result.returncode})")

        if result.stdout.strip():
            print(f"  " + "-" * 30)
            print(f"  输出:")
            for line in result.stdout.strip().split("\n")[:10]:
                print(f"    {line}")
            if len(result.stdout.strip().split("\n")) > 10:
                print(f"    ... (输出过长，已截断)")

        if result.stderr.strip():
            print(f"  错误输出:")
            for line in result.stderr.strip().split("\n")[:5]:
                print(f"    {line}")

    except subprocess.TimeoutExpired:
        print(f"  耗时: >60 秒 (超时)")
        print(f"  状态: 超时，已终止")
    except FileNotFoundError:
        print(f"  运行失败: 找不到解释器 ({cmd[0]})")
    except Exception as e:
        print(f"  运行失败: {e}")

    print()