"""wocli progress - 假进度条"""

import sys
import time
import random
import signal
from wocli import terminal


def run():
    """运行 progress 命令."""
    # 获取任务名
    tasks = [
        "正在编译内核模块",
        "正在同步区块链数据",
        "正在训练神经网络",
        "正在破解WiFi密码",
        "正在生成毕业论文",
        "正在sudo rm -rf/*",
        "正在优化数据库索引",
        "正在下载舍友电脑的学习资料",
        "正在删除System32",
        "正在入侵教务系统改成绩",
    ]

    if len(sys.argv) > 1:
        task = " ".join(sys.argv[1:])
    else:
        task = random.choice(tasks)

    print()
    print(f"  {task}...")
    print()
    terminal.hide_cursor()

    running = True
    def stop(signum, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    progress = 0
    width = 40
    try:
        while running:
            progress += random.uniform(0.3, 2.5)
            if progress > 95:
                progress = random.uniform(95, 99.5)
            filled = int(width * progress / 100)
            bar = "=" * filled + ">" + " " * (width - filled - 1)
            eta = random.randint(1, 999)
            sys.stdout.write(f"\r  [{bar}] {progress:.1f}%  ETA: {eta}s")
            sys.stdout.flush()
            time.sleep(random.uniform(0.1, 0.5))
    except:
        pass
    finally:
        terminal.show_cursor()
        print()
        print()