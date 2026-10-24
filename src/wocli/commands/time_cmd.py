"""wocli time - 测试代码运行耗时."""

import subprocess
import time
import sys
import os


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
        # Windows 上通常没有 python3 命令，用当前解释器保证跨平台
        ".py": [sys.executable, filepath],
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
    print("  正在运行...")

    try:
        start = time.perf_counter()
        # errors="replace"：子进程输出 GBK 等非 UTF-8 字节时不能崩
        result = subprocess.run(
            cmd, capture_output=True, text=True, errors="replace", timeout=60)
        elapsed = time.perf_counter() - start
        print(f"  耗时：{elapsed:.3f} 秒")
        if result.returncode == 0:
            print("  状态：运行成功")
        else:
            print(f"  状态：运行失败 (退出码 {result.returncode})")

        # 失败时 stderr 才是重点（报错堆栈都在那），成功时看 stdout
        tail = result.stdout.strip()
        label = "  输出："
        if result.returncode != 0 and result.stderr.strip():
            tail = result.stderr.strip()
            label = "  错误输出："
        if tail:
            print(label)
            for line in tail.split("\n")[:10]:
                print(f"    {line}")
    except subprocess.TimeoutExpired:
        print("  耗时：>60 秒（超时）")
    except FileNotFoundError:
        print(f"  找不到解释器：{cmd[0]}")
    print()