"""wocli regex - 正！则！."""

import json
import re
import subprocess
import sys

# (a+)+$ 这类嵌套量词遇长文本会灾难性回溯，一次匹配能算几分钟。
# re 没法中断：把匹配丢进线程限时等也没用——正则引擎在 C 层不吐 GIL，
# 主线程的 wait(0.5) 实测会被硬拖到匹配结束（2.7 秒）才返回。
# 所以放到子进程里跑，超时直接杀进程。
MATCH_TIMEOUT_SECONDS = 5
MAX_MATCHES = 10000

# 子进程里的匹配器：读 JSON（表达式 + 文本 + 上限），回 JSON（匹配列表）
_MATCHER = """
import json, re, sys
payload = json.loads(sys.stdin.read())
regex = re.compile(payload["pattern"])
found = []
truncated = False
for match in regex.finditer(payload["text"]):
    found.append([match.start(), match.end(), match.group()])
    if len(found) >= payload["limit"]:
        truncated = True
        break
sys.stdout.write(json.dumps({"matches": found, "truncated": truncated}))
"""


def find_matches(pattern, text):
    """子进程限时匹配，返回 (matches, truncated, error).

    error 为 None 表示成功；"timeout" 表示灾难性回溯超时；
    其他值是子进程的报错信息。
    """
    payload = json.dumps(
        {"pattern": pattern, "text": text, "limit": MAX_MATCHES})
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _MATCHER],
            input=payload, capture_output=True, text=True,
            timeout=MATCH_TIMEOUT_SECONDS, errors="replace",
        )
    except subprocess.TimeoutExpired:
        return [], False, "timeout"
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        return [], False, detail[-1] if detail else f"退出码 {proc.returncode}"
    data = json.loads(proc.stdout)
    return data["matches"], data["truncated"], None


def run():
    if len(sys.argv) < 2:
        print("\n  用法：wocli regex '<正则表达式>'\n")
        return

    pattern = sys.argv[1]
    try:
        re.compile(pattern)
    except re.error as e:
        print(f"\n  正则无效：{e}\n")
        return

    print()
    print(f"  表达式：{pattern}")
    print("  输入文本（Ctrl+D 结束；Windows 用 Ctrl+Z 再回车）：")

    try:
        text = sys.stdin.read().strip()
    except KeyboardInterrupt:
        print()
        return

    if not text:
        print("  未输入文本。\n")
        return

    matches, truncated, error = find_matches(pattern, text)
    if error == "timeout":
        print("\n  匹配超时：这个表达式大概率发生了灾难性回溯（嵌套量词最常见）。")
        print("  换个更具体的写法、或缩短输入文本再试。\n")
        return
    if error:
        print(f"\n  匹配出错：{error}\n")
        return

    for count, (start, end, group) in enumerate(matches, 1):
        print(f"  匹配 {count}：位置 {start}-{end}  {group}")

    print(f"\n  共 {len(matches)} 处匹配。")
    if truncated:
        print(f"  （结果太多，只显示前 {MAX_MATCHES} 个）")
    print()
