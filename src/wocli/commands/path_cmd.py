"""wocli path - Display PATH environment variable."""

import os
import shutil


def run():
    """Run the path command."""
    paths = os.environ.get("PATH", "").split(":")

    print()
    print("  [ PATH Environment ]")
    print()

    for i, p in enumerate(paths, 1):
        if not p:
            continue

        exists = os.path.isdir(p)
        marker = "" if exists else "  [missing]"
        exe_count = 0
        if exists:
            try:
                for f in os.listdir(p):
                    fp = os.path.join(p, f)
                    if os.access(fp, os.X_OK) and not os.path.isdir(fp):
                        exe_count += 1
            except Exception:
                pass

        print(f"  {i:2d}. {p}{marker}")
        if exists and exe_count > 0:
            print(f"      ({exe_count} executables)")

    print()
    print(f"  Total: {len([p for p in paths if p])} entries")
    print()