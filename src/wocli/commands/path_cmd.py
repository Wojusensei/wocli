"""wocli path - Display PATH environment variable."""

import os
import platform

# Windows 上 os.access(X_OK) 对普通文件基本恒为 True（CPython 文档写明的行为），
# 按扩展名判断才靠得住
WINDOWS_EXEC_SUFFIXES = (".exe", ".cmd", ".bat", ".com", ".ps1")


def count_executables(path):
    """统计目录里的可执行文件数，读不了的目录按 0 处理."""
    count = 0
    try:
        names = os.listdir(path)
    except OSError:
        return 0
    if platform.system() == "Windows":
        for name in names:
            if name.lower().endswith(WINDOWS_EXEC_SUFFIXES):
                count += 1
        return count
    for name in names:
        full = os.path.join(path, name)
        if os.access(full, os.X_OK) and not os.path.isdir(full):
            count += 1
    return count


def run():
    """Run the path command."""
    paths = os.environ.get("PATH", "").split(os.pathsep)

    print()
    print("  [ PATH Environment ]")
    print()

    for i, p in enumerate(paths, 1):
        if not p:
            continue

        exists = os.path.isdir(p)
        marker = "" if exists else "  [missing]"
        exe_count = count_executables(p) if exists else 0

        print(f"  {i:2d}. {p}{marker}")
        if exists and exe_count > 0:
            print(f"      ({exe_count} executables)")

    print()
    print(f"  Total: {len([p for p in paths if p])} entries")
    print()
