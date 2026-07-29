"""wocli sys - Show system status with animated bars."""

import platform
import os
import time
import sys


def get_cpu_usage():
    """Get CPU usage percentage."""
    try:
        if platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["top", "-l", "1", "-n", "0"],
                capture_output=True, text=True
            )
            for line in result.stdout.split("\n"):
                if "CPU usage" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        nums = parts[1].split(",")
                        user = float(nums[0].strip().replace("%", ""))
                        sys_cpu = float(nums[1].strip().replace("%", "")) if len(nums) > 1 else 0
                        return min(user + sys_cpu, 100)
        elif platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage"],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                return float(lines[1].strip())
        else:
            import subprocess
            result = subprocess.run(
                ["top", "-bn1"],
                capture_output=True, text=True
            )
            for line in result.stdout.split("\n"):
                if "Cpu(s)" in line:
                    parts = line.split(":")[1].split(",")
                    return float(parts[0].strip().replace("%us", "").replace("%id", ""))
    except Exception:
        pass
    return 0


def get_memory_usage():
    """Get memory usage."""
    try:
        if platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")
            page_size = 4096
            free = 0
            active = 0
            wired = 0
            for line in lines:
                if "page size" in line:
                    page_size = int(line.split(":")[1].strip())
                if "Pages free" in line:
                    free = int(line.split(":")[1].strip().replace(".", ""))
                if "Pages active" in line:
                    active = int(line.split(":")[1].strip().replace(".", ""))
                if "Pages wired" in line:
                    wired = int(line.split(":")[1].strip().replace(".", ""))
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") if hasattr(os, 'sysconf') else 16 * 1024 * 1024 * 1024
            used = (active + wired) * page_size
            return used, total
        elif platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory"],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 2:
                    total = int(parts[0]) * 1024
                    free_mem = int(parts[1]) * 1024
                    return total - free_mem, total
        else:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
            total = 0
            available = 0
            for line in meminfo.split("\n"):
                if "MemTotal" in line:
                    total = int(line.split()[1]) * 1024
                if "MemAvailable" in line:
                    available = int(line.split()[1]) * 1024
            if total > 0:
                return total - available, total
    except Exception:
        pass
    return 0, 1


def get_disk_usage():
    """Get disk usage."""
    try:
        stat = os.statvfs(os.path.expanduser("~"))
        total = stat.f_frsize * stat.f_blocks
        free = stat.f_frsize * stat.f_bfree
        used = total - free
        return used, total
    except Exception:
        return 0, 1


def format_bytes(size_bytes):
    """Convert bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f}PB"


def draw_bar(label, used, total, width=30):
    """Draw an animated progress bar."""
    pct = used / total if total > 0 else 0
    filled = int(width * pct)
    bar = "=" * filled + ">" + " " * (width - filled - 1)
    used_str = format_bytes(used) if total > 1024 else f"{pct:.0%}"
    total_str = format_bytes(total) if total > 1024 else ""
    if total_str:
        return f"  {label:<6} [{bar}] {used_str} / {total_str}"
    return f"  {label:<6} [{bar}] {pct:.0%}"


def run():
    print(f"\n  系统状态 · {platform.system()} {platform.release()}")
    print()

    for _ in range(3):
        cpu = get_cpu_usage()
        mem_used, mem_total = get_memory_usage()
        disk_used, disk_total = get_disk_usage()

        print(f"  CPU  {'=' * int(30 * cpu / 100):<30} {cpu:.0f}%")
        print(draw_bar("内存", mem_used, mem_total))
        print(draw_bar("磁盘", disk_used, disk_total))

        if _ < 2:
            time.sleep(1)
            sys.stdout.write("\033[3A")
            sys.stdout.flush()

    print()