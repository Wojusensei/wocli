# 命令系统

这份文档说明 wocli 的两层命令入口、驾驶舱里的斜杠命令、命令注册方式，以及从 0.7.x 升级到 v1.0.0 时需要注意的变化。

## 1. 两层入口

### CLI 子命令

```bash
wocli                 # TTY 下直接打开驾驶舱；非 TTY 打印帮助
wocli help            # 打印传统命令列表
WOCLI_NO_TUI=1 wocli  # 明确只要帮助页
wocli tui             # 显式打开驾驶舱
wocli --theme neon    # 等价于 wocli tui --theme neon
wocli shell           # tui 的别名
wocli cockpit         # tui 的别名
wocli <命令> [参数]    # 原有命令，例如 wocli ip、wocli matrix 你好
wocli version         # 版本号
```

`wocli` 无参数的行为是 v1.0.0 的破坏性变化：以前一定打印帮助，现在在交互式终端里会进入驾驶舱。脚本、CI、管道里仍然打印帮助，因为 `stdin`/`stdout` 不是 TTY。

需要旧行为时：

```bash
wocli help
# 或
WOCLI_NO_TUI=1 wocli
```

### 驾驶舱内的斜杠命令

进入驾驶舱后，输入分为两类：

**驾驶舱自己的命令**（不会出现在 `wocli help` 的子命令表里）：

| 命令 | 作用 |
|---|---|
| `/status`、`/context` | 系统上下文面板（内存 waffle、CPU、磁盘、电池、WiFi、Git） |
| `/help`、`?` | 命令列表与快捷键 |
| `/theme [名称]` | 切换主题；不带参数时循环。可选 `catppuccin`、`neon`、`amber`、`paper`、`auto` |
| `/mode [名称]` | 切换人格模式；不带参数时循环。可选 `正常`、`整活`、`死机`，也支持 `normal`/`fun`/`dead` |
| `/doctor` | 终端、Python、prompt_toolkit、主题、配置路径诊断 |
| `/clear` | 清屏并重绘欢迎界面 |
| `/version` | 显示版本号 |
| `/goodbye` | 播放花式退出动画，然后退出驾驶舱 |
| `/quit`、`/exit`、`q` | 退出驾驶舱 |

**注册表里的原有命令**：

```text
/ip      /cow 你好     /matrix ...     /sys
/theme   /mode         /badapple       /chat
```

斜杠可带可不带。带参数时按 shell 规则切分（`shlex`），所以：

```text
/cow 你好 世界
/theme neon
/regex '\d+'
```

## 2. 补全、历史和快捷键

- 输入 `/`：打开多列命令表。一屏能看大部分命令，底部显示当前选中项的描述。
- `↑` / `↓`：在命令表里移动；`Tab`：补全当前项；`Esc`：关闭菜单。
- `Ctrl+K`：打开命令面板（插入 `/` 并展开补全）。
- `Ctrl+R`、`↑`：翻历史；历史在 `~/.wocli_history`。
- `Shift+Tab`：循环人格模式。
- `Ctrl+C`：有输入时清空；空输入时连按两次退出。
- `Ctrl+D`：退出。
- 补全菜单只在打开时占用屏幕空间，关闭后 `/status` 面板仍然从顶部完整绘制。

## 3. 命令注册表

CLI 和 TUI 共用一份表，位于 `src/wocli/registry.py`：

```python
COMMANDS = {
    "ip": (ip.run, "查看网络信息 ..."),
    "tui": (run_tui, "驾驶舱 TUI ..."),
}

HELP_GROUPS = {
    "效率": ["tui", "port", "tree", ...],
    "发电": [...],
}

ALIASES = {
    "shell": "tui",
    "cockpit": "tui",
}
```

- `COMMANDS[name] = (callable, description)`：description 会出现在 `wocli help` 和 TUI 补全菜单里。
- `HELP_GROUPS` 控制 `wocli help` 的分组；TUI 的 `/help` 也用它。
- `ALIASES` 只影响 CLI 入口，不会重复出现在补全菜单里。
- `main.py` 继续 re-export `COMMANDS` 和 `HELP_GROUPS`，旧代码 `from wocli.main import COMMANDS` 仍然可用。
- `tui` 入口在 `registry.run_tui` 里延迟导入 `wocli.tui`，没装 prompt_toolkit 时其它命令不受影响。

### 新增一个命令

1. 在 `src/wocli/commands/` 新建模块，实现 `run()`。
2. 在 `registry.py` 导入模块，加入 `COMMANDS`，并放进合适的 `HELP_GROUPS`。
3. 如果要在 TUI 里用参数，按老约定读 `sys.argv[1:]`；TUI 调用时会设置成 `[命令名] + 参数`。
4. 补测试，并确认 `wocli help` 和 TUI 的 `/` 菜单都能看到它。

TUI 里的命令分发顺序：

1. 驾驶舱本地命令（`status`、`help`、`theme`、`mode`、`doctor`、`clear`、`version`、`quit`）。
2. `COMMANDS` 里的注册命令。
3. 未知命令：给出最接近的拼写建议。

## 4. 从 0.7.x 升级

### 破坏性变化

- `wocli` 无参数在交互式终端下进入驾驶舱，不再打印帮助。
- 需要帮助页：`wocli help` 或 `WOCLI_NO_TUI=1 wocli`。
- 新增运行时依赖 `prompt_toolkit>=3.0`。

### 兼容的部分

- 所有原有子命令名称、参数和行为不变。
- `wocli ip`、`wocli sys`、`wocli matrix ...` 等脚本调用不受影响。
- 在非 TTY 环境（CI、管道、重定向）下，裸 `wocli` 仍然打印帮助。

### 推荐迁移

```bash
# 脚本里原来依赖 wocli 打印帮助
wocli help

# 明确进入驾驶舱
wocli tui

# 不需要 TUI 的环境
WOCLI_NO_TUI=1 wocli
```
