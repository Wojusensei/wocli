"""wocli hash - 计算文件 MD5 / SHA256."""

import hashlib
import sys
import os


def compute_hashes(filepath):
    """单次读取同时算 MD5 和 SHA256，大文件不用扫两遍."""
    md5 = hashlib.new("md5")
    sha256 = hashlib.new("sha256")
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                md5.update(chunk)
                sha256.update(chunk)
        return md5.hexdigest(), sha256.hexdigest()
    # OSError 兜住文件消失/无权限；ValueError 兜住 FIPS 模式禁用 md5 的机器
    except (OSError, ValueError):
        return None, None


def run():
    if len(sys.argv) < 2:
        print("\n  用法：wocli hash <文件路径>\n")
        return

    filepath = sys.argv[1]
    if os.path.isdir(filepath):
        print(f"\n  这是个目录，请传文件路径：{filepath}\n")
        return
    if not os.path.isfile(filepath):
        print(f"\n  文件不存在：{filepath}\n")
        return

    print()
    print(f"  文件：{os.path.basename(filepath)}")
    md5, sha256 = compute_hashes(filepath)
    print(f"  MD5：    {md5 if md5 else '计算失败'}")
    print(f"  SHA256： {sha256 if sha256 else '计算失败'}")
    print()