"""pytest 公共准备.

把工作区的 src 放到 sys.path 最前面：本地跑测试时，venv 里可能装着旧版 wocli，
要测的始终是这份源码（CI 里是用 pip install -e . 装的，效果一样）。
"""
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

for path in (SRC_DIR, TESTS_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)
