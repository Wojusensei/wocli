"""wocli time - 测试代码运行耗时."""

import subprocess
import time
import sys
import os
import platform


def run():
    if len(sys.argv) < 2:
        print("\n  用法：wocli time <文件路径>\n")
        return

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"\n  文件不存在：{filepath}\n")
        return

    filename = os.path.basename(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    commands_map = {
        ".py": ["python3", filepath],
        ".js": ["node", filepath],
        ".sh": ["bash", filepath],
        ".rb": ["ruby", filepath],
        ".pl": ["perl", filepath],
    }

    if ext in commands_map:
        cmd = commands_map[ext]
    elif os.access(filepath, os.X_OK):
        cmd = [filepath]
    else:
        print(f"\n  不支持的文件类型：{ext}\n")
        return

    print()
    print(f"  文件：{filename}")
    print(f"  正在运行...")

    try:
        start = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        elapsed = time.perf_counter() - start
        print(f"  耗时：{elapsed:.3f} 秒")
        print(f"  状态：{'运行成功' if result.returncode == 0 else f'运行失败 (退出码 {result.returncode})'}")
        if result.stdout.strip():
            print(f"  输出：")
            for line in result.stdout.strip().split("\n")[:10]:
                print(f"    {line}")
    except subprocess.TimeoutExpired:
        print(f"  耗时：>60 秒（超时）")
    except FileNotFoundError:
        print(f"  找不到解释器：{cmd[0]}")
    print()