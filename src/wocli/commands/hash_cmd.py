"""wocli hash - 计算文件 MD5 / SHA256."""

import hashlib
import sys
import os


def compute_hash(filepath, algo):
    """计算文件哈希值."""
    h = hashlib.new(algo)
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return None
    except PermissionError:
        return None


def run():
    """运行 hash 命令."""
    if len(sys.argv) < 2:
        print("\n  用法: wocli hash <文件路径>\n")
        return

    filepath = sys.argv[1]

    if not os.path.isfile(filepath):
        print(f"\n  文件不存在: {filepath}\n")
        return

    print()
    print(f"  [ 文件哈希 ]")
    print(f"  文件: {os.path.basename(filepath)}")
    print(f"  " + "-" * 50)

    md5 = compute_hash(filepath, "md5")
    sha256 = compute_hash(filepath, "sha256")

    if md5:
        print(f"  MD5:     {md5}")
    else:
        print(f"  MD5:     计算失败")

    if sha256:
        print(f"  SHA256:  {sha256}")
    else:
        print(f"  SHA256:  计算失败")

    print()