"""wocli ip - Show network information."""

import socket
import subprocess
import platform


def get_local_ip():
    """Get local IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "Unknown"


def get_ipv6():
    """Get IPv6 address."""
    try:
        addrs = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET6)
        for addr in addrs:
            ip = addr[4][0]
            if not ip.startswith("::1") and not ip.startswith("fe80"):
                return ip
        for addr in addrs:
            ip = addr[4][0]
            if ip.startswith("fe80"):
                return ip
    except Exception:
        pass
    return "Unknown"


def get_gateway_macos():
    """Get default gateway on macOS."""
    try:
        result = subprocess.run(
            ["netstat", "-rn"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "default" in line:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
    except Exception:
        pass
    return "Unknown"


def get_gateway_windows():
    """Get default gateway on Windows."""
    try:
        result = subprocess.run(
            ["ipconfig"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "Default Gateway" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    val = parts[1].strip()
                    if val:
                        return val
    except Exception:
        pass
    return "Unknown"


def get_gateway_linux():
    """Get default gateway on Linux."""
    try:
        result = subprocess.run(
            ["ip", "route"],
            capture_output=True, text=True
        )
        for line in result.stdout.split("\n"):
            if "default" in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
    except Exception:
        pass
    return "Unknown"


def get_gateway():
    """Get default gateway, cross-platform."""
    system = platform.system()
    if system == "Darwin":
        return get_gateway_macos()
    elif system == "Windows":
        return get_gateway_windows()
    else:
        return get_gateway_linux()


def get_public_ip():
    """Get public IP address."""
    try:
        import urllib.request
        response = urllib.request.urlopen("https://api.ipify.org", timeout=5)
        return response.read().decode().strip()
    except Exception:
        try:
            import urllib.request
            response = urllib.request.urlopen("https://ifconfig.me", timeout=5)
            return response.read().decode().strip()
        except Exception:
            return "Unknown"


def run():
    """Run the ip command."""
    local_ip = get_local_ip()
    ipv6 = get_ipv6()
    gateway = get_gateway()
    public_ip = get_public_ip()

    print()
    print("  [ Network Info ]")
    print("  +-----------------------------+")
    print(f"  | {'IPv4':<10} {local_ip:<15} |")
    print(f"  | {'IPv6':<10} {ipv6:<15} |")
    print(f"  | {'Gateway':<10} {gateway:<15} |")
    print(f"  | {'Public':<10} {public_ip:<15} |")
    print("  +-----------------------------+")
    print()