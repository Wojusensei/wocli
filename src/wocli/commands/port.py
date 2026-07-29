"""wocli port - 查看端口占用."""

import subprocess
import platform


def get_ports_macos():
    try:
        result = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-n", "-P"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        ports = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 9:
                proc = parts[0]
                addr = parts[8]
                if ":" in addr:
                    port = addr.split(":")[-1]
                    ports.append((port, proc))
        return ports
    except Exception:
        return []


def get_ports_windows():
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        ports = []
        for line in lines:
            if "LISTENING" in line:
                parts = line.split()
                addr = parts[1]
                pid = parts[-1]
                if ":" in addr:
                    port = addr.split(":")[-1]
                    try:
                        proc_result = subprocess.run(
                            ["tasklist", "/FI", f"PID eq {pid}"],
                            capture_output=True, text=True
                        )
                        proc_lines = proc_result.stdout.strip().split("\n")
                        proc = proc_lines[-1].split()[0] if len(proc_lines) > 1 else pid
                    except Exception:
                        proc = pid
                    ports.append((port, proc))
        return ports
    except Exception:
        return []


def get_ports_linux():
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        ports = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 5:
                addr = parts[3]
                proc_info = parts[-1]
                if ":" in addr:
                    port = addr.split(":")[-1]
                    proc = proc_info.split('"')[1] if '"' in proc_info else proc_info
                    ports.append((port, proc))
        return ports
    except Exception:
        return []


def run():
    system = platform.system()
    if system == "Darwin":
        ports = get_ports_macos()
    elif system == "Windows":
        ports = get_ports_windows()
    else:
        ports = get_ports_linux()

    if not ports:
        print("\n  没有发现监听端口。\n")
        return

    print()
    print("  [ 端口占用 ]")
    print("  +----------+---------------------------+")
    print(f"  | {'端口':<8} | {'进程':<25} |")
    print("  +----------+---------------------------+")
    seen = set()
    for port, proc in ports:
        if port not in seen:
            seen.add(port)
            print(f"  | {port:<8} | {proc:<25} |")
    print("  +----------+---------------------------+")
    print()