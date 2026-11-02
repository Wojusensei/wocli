# Changelog

## v1.0.0（2026-11-02）

驾驶舱 TUI 首次发布，命令系统分层整理。

### 新增

- `wocli tui`，以及 `wocli shell` / `wocli cockpit` 别名。
- 直接运行 `wocli` 在交互式终端下进入驾驶舱。
- 驾驶舱 HUD：版本、目录、Git 分支/改动、电量、WiFi、CPU、运行时长、时钟。
- `/status` 系统上下文面板：100 格内存 waffle、CPU、磁盘、电池健康、WiFi、Git。
- 主题：Catppuccin Mocha、赛博霓虹、琥珀 CRT、纸白 Paper，以及按终端背景自动选择的 `auto`。
- 人格模式：正常、整活、死机；`Shift+Tab` 循环。
- 斜杠命令多列补全、上下键浏览、选中项描述、历史、`Ctrl+K` 命令面板。
- 跨平台自适应：macOS 显示真实系统版本，Windows 识别 10/11 与 build，Linux 读发行版名，WSL 单独标注。
- `--ascii` 强制 ASCII 图元；终端不支持 Unicode 时自动回退。
- `--no-boot` 跳过开机自检；主题/模式持久化到 `~/.wocli_tui.json`。

### 变更

- 命令注册表从 `main.py` 抽到 `src/wocli/registry.py`。
- `main.py` 继续 re-export `COMMANDS` / `HELP_GROUPS`，旧导入路径可用。
- `HELP_GROUPS` 增加 `tui`；新增 `ALIASES` 表。
- README 的贡献指引改为在 `registry.py` 注册新命令。
- 新增运行时依赖 `prompt_toolkit>=3.0`。

### 破坏性变化

- `wocli` 无参数在 TTY 下不再打印帮助，而是进入驾驶舱。
- 脚本/CI 需要帮助页时改用 `wocli help` 或 `WOCLI_NO_TUI=1 wocli`。
- 非 TTY 环境仍保持打印帮助。

### 修复 / 体验

- 补全菜单改为多列网格，输入 `/` 可以一屏看到完整命令表，`↑↓` 浏览、`Tab` 补全、`Esc` 关闭。
- 补全菜单只在打开时占用空间，关闭后 `/status` 面板不会被顶出视口。
- 斜杠命令不再显示历史幽灵补全，避免输入 `/` 时看起来像带着旧命令。
- `/goodbye` 在驾驶舱里播放完退出动画后会直接退出，不再回到提示符。
- `wocli --theme neon` 等 TUI 参数可以直接跟在裸命令后面，等价于 `wocli tui ...`。
- 状态栏按优先级自适应宽度，窄终端自动省略低优先级信息。

## 更早版本

0.7.x 及以前未维护 changelog，变更见 Git 历史。
