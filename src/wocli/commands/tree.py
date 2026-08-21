"""wocli tree - 显示文件夹结构."""

import os
import sys


def get_size_str(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def tree(dir_path, prefix="", max_depth=3, current_depth=0, stats=None):
    if stats is None:
        stats = [0, 0]  # [目录数, 文件数]，跨递归层级累计
    if current_depth >= max_depth:
        return

    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        print(f"{prefix}[denied]")
        return
    except FileNotFoundError:
        print(f"{prefix}[not found]")
        return

    for i, entry in enumerate(entries):
        full_path = os.path.join(dir_path, entry)
        is_last = (i == len(entries) - 1)
        connector = "`-- " if is_last else "|-- "
        next_prefix = "    " if is_last else "|   "

        if os.path.isdir(full_path):
            stats[0] += 1
            print(f"{prefix}{connector}{entry}/")
            tree(full_path, prefix + next_prefix, max_depth, current_depth + 1, stats)
        else:
            stats[1] += 1
            try:
                size = os.path.getsize(full_path)
                size_str = get_size_str(size)
            except OSError:
                size_str = "?"
            print(f"{prefix}{connector}{entry} ({size_str})")

    if current_depth == 0:
        print(f"\n  {stats[0]} 个目录, {stats[1]} 个文件")


def run():
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    target = os.path.abspath(target)

    print(f"\n  {target}")
    tree(target)
    print()