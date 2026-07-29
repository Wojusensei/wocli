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
    if len(sys.argv) < 2:
        print("\n  用法：wocli hash <文件路径>\n")
        return

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"\n  文件不存在：{filepath}\n")
        return

    print()
    print(f"  文件：{os.path.basename(filepath)}")
    md5 = compute_hash(filepath, "md5")
    sha256 = compute_hash(filepath, "sha256")
    print(f"  MD5：    {md5 if md5 else '计算失败'}")
    print(f"  SHA256： {sha256 if sha256 else '计算失败'}")
    print()