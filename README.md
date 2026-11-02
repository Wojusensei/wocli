# wocli

wocli 是一个终端工具集合，提供系统信息、网络诊断、文本处理、终端娱乐和局域网聊天等命令。支持 macOS、Windows 和部分 Linux 发行版。

命令分为两层：顶层 `wocli` 子命令，以及驾驶舱 TUI 内的斜杠命令。命令注册和扩展方式见 [docs/command-system.md](docs/command-system.md)。

## 安装

要求 Python 3.9 或更高版本。

```bash
pip install wocli
```

macOS 若提示 `externally-managed-environment`：

```bash
python3 -m venv wocli_env
source wocli_env/bin/activate
pip install wocli
```

Windows 若提示找不到 `wocli`，将 Python 的 `Scripts` 目录加入 `PATH`。

从源码安装：

```bash
pip install -e .
```

> 注意：`pip install -e .` 偶尔不会重新解析依赖。缺少 colorama、prompt_toolkit 或 qrcode 时，需要手动安装。

## 快速开始

在交互式终端中运行：

```bash
wocli
```

进入驾驶舱。查看命令列表：

```bash
wocli help
```

运行单个命令：

```bash
wocli ip
wocli sys
wocli cow 你好
```

在管道、脚本或 CI 中，裸 `wocli` 打印帮助，不进入 TUI。需要强制打印帮助时：

```bash
WOCLI_NO_TUI=1 wocli
```

## 驾驶舱

`wocli tui` 打开驾驶舱。在 TTY 中，裸 `wocli` 与之等价。别名：`wocli shell`、`wocli cockpit`。

```bash
wocli tui
wocli tui --theme neon --mode 整活
wocli tui --no-boot
wocli tui --ascii
wocli --theme neon
```

`wocli --theme neon` 等价于 `wocli tui --theme neon`。

选项：

| 选项 | 说明 |
|---|---|
| `--theme {catppuccin,neon,amber,paper,auto}` | 指定主题；`auto` 根据终端背景选择深色或浅色主题 |
| `--mode {正常,整活,死机,normal,fun,chaos,dead}` | 指定人格模式 |
| `--no-boot` | 跳过开机自检动画 |
| `--ascii` | 强制使用 ASCII 图元 |

驾驶舱包含：

- 输入框上方的状态栏，显示版本、当前目录、Git 分支和改动、电量、WiFi 信号、CPU、运行时长和时钟。终端宽度不足时，状态栏按优先级省略低优先级字段。
- `/status` 系统上下文面板，显示内存 waffle 图、CPU、磁盘、电池、WiFi 和 Git。
- 多列命令补全、历史记录和快捷键。

### 驾驶舱命令

| 命令 | 说明 |
|---|---|
| `/status`、`/context` | 显示系统上下文面板 |
| `/help`、`?` | 显示命令列表和快捷键 |
| `/theme [名称]` | 切换主题；省略名称时循环切换 |
| `/mode [名称]` | 切换人格模式；省略名称时循环切换 |
| `/doctor` | 显示终端、Python、prompt_toolkit、主题和配置路径 |
| `/clear` | 清屏并重绘欢迎界面 |
| `/version` | 显示版本号 |
| `/goodbye` | 播放退出动画并退出驾驶舱 |
| `/quit`、`/exit`、`q` | 退出驾驶舱 |

注册表中的命令可以直接在驾驶舱中运行。斜杠可省略：

```text
/ip
/sys
/cow 你好
/regex '\d+'
```

参数按 shell 规则切分。

### 快捷键

| 按键 | 操作 |
|---|---|
| `/` | 打开命令表 |
| `↑`、`↓` | 在命令表中移动 |
| `Tab` | 补全当前项 |
| `Esc` | 关闭命令表 |
| `Ctrl+K` | 打开命令面板 |
| `Ctrl+R`、`↑` | 浏览历史 |
| `Shift+Tab` | 循环人格模式 |
| `Ctrl+C` | 有输入时清空；空输入时连按两次退出 |
| `Ctrl+D` | 退出 |

### 主题

| 名称 | 说明 |
|---|---|
| `catppuccin` | Catppuccin Mocha 深色主题 |
| `neon` | 高对比霓虹主题 |
| `amber` | 琥珀色 CRT 主题 |
| `paper` | 浅色纸白主题 |
| `auto` | 根据 `TERM_BACKGROUND` 或 `COLORFGBG` 选择 `catppuccin` 或 `paper`；无法判断时使用 `catppuccin` |

### 人格模式

| 模式 | 外观 |
|---|---|
| `正常` | `❯` 提示符，静态配色 |
| `整活` | `✦` 提示符，强调色轮换，状态栏显示每日运势 |
| `死机` | `▓` 提示符，红色状态栏，随机故障字符 |

人格模式只影响提示符、配色和状态栏显示，不改变命令行为。

### 配置文件

| 路径 | 内容 |
|---|---|
| `~/.wocli_tui.json` | 主题和人格模式 |
| `~/.wocli_history` | 命令历史 |

## 命令参考

以下命令均通过 `wocli <命令> [参数]` 调用，也可以带斜杠在驾驶舱中运行。

### 学习

| 命令 | 说明 |
|---|---|
| `wocli ip` | 显示内网 IPv4/IPv6、默认网关（含 IPv6 网关与出口网卡）和公网 IPv4/IPv6。 |
| `wocli chat` | 局域网聊天。默认端口 52020，可用 `--port` 指定；连接自定义端口时写成 `IP:端口`。服务端最多等待 10 分钟，客户端连接失败时重试 30 秒。新旧版本使用不同握手协议，不能互通。 |

### 效率

| 命令 | 说明 |
|---|---|
| `wocli tui` | 打开驾驶舱。 |
| `wocli port` | 显示当前端口占用。 |
| `wocli tree` | 以树形显示当前目录结构，并标注文件大小。 |
| `wocli sys` | 显示 CPU、内存和磁盘使用率，带动态进度条。 |
| `wocli path` | 列出 `PATH` 环境变量，并标注不存在的路径。 |
| `wocli battery` | 显示电池信息、循环次数、最大容量和健康评分。 |
| `wocli wifi` | 显示 WiFi 名称、信号强度、信道、加密方式和协商速率。 |
| `wocli count` | 统计文本词数。`-cn` 统计中文字数，`-en` 统计英文单词数；多行输入以单独一行 `_over_` 结束。 |

### 发电

| 命令 | 说明 |
|---|---|
| `wocli gpa` | 交互式加权 GPA 计算器，附带评语。 |
| `wocli luck` | 随机显示编程运势、幸运语言和 bug 指数。 |
| `wocli matrix 文本...` | 数字雨动画，输入的文本会出现在雨中。按 Ctrl+C 退出。 |
| `wocli lolcat 文本` | 以彩虹渐变输出文本。 |
| `wocli typing` | 打字速度测试，输出 WPM 和评级。 |
| `wocli progress` | 假进度条动画。按 Ctrl+C 退出。 |
| `wocli qr [--svg 文件] [--compact] 文本或链接` | 在终端生成二维码。`--svg` 导出 SVG 图片；`--compact` 强制紧凑渲染。 |
| `wocli goodbye` | 播放退出动画。在驾驶舱中执行后退出驾驶舱。 |
| `wocli cow 文本` | 使用 ASCII 牛显示文本。 |
| `wocli glitch 文本` | 输出故障风文本。 |
| `wocli dead` | 模拟终端死机、花屏和恢复。 |
| `wocli badapple` | 播放 Bad Apple ASCII 动画（6572 帧）。首次运行下载帧序列（约 4.6 MB）并缓存；可选下载配乐。可用 `wocli badapple <帧目录或文件>` 或环境变量 `WOCLI_BADAPPLE_FRAMES` 指定帧源。部分播放器不支持音频。 |

### 编程

| 命令 | 说明 |
|---|---|
| `wocli time 文件` | 测试代码运行耗时。 |
| `wocli hash 文件` | 计算文件的 MD5 和 SHA256。 |
| `wocli regex 表达式` | 正则表达式测试器；匹配在子进程中运行并带超时。 |

## 平台说明

### macOS

- macOS 14 及以上会对 WiFi 名称和 BSSID 打码。需要给终端开启定位权限（系统设置 → 隐私与安全性 → 定位服务）才能显示这两项。信号强度、信道、加密方式和速率不受影响。
- 电池循环次数和最大容量来自 `pmset` 与 `ioreg`。
- CPU 使用率取 `top` 的第二份采样。

### Windows

- 电池循环次数和最大容量来自 `powercfg` 电池报告，首次查询可能需要一两秒。
- 系统版本根据 build 号区分 Windows 10 和 Windows 11。
- 没有无线网卡时，WiFi 相关字段显示未获取。

### Linux

- 发行版名称读取 `/etc/os-release`。
- WiFi 信息按 `nmcli`、`iw`、`/proc/net/wireless`、`iwconfig` 的顺序获取。
- 电池信息读取 `/sys/class/power_supply`。
- WSL 环境会在系统名称中标注。

### 终端兼容性

- 颜色深度自动检测为 truecolor、256 色、16 色或无色。
- 终端不支持 Unicode 时自动使用 ASCII 图元；也可以使用 `--ascii` 强制启用。
- 浅色终端可以使用 `--theme paper`，或使用 `--theme auto` 自动选择。

## 开发

安装开发依赖并运行测试：

```bash
python -m pip install -e .
pytest
```

运行 CI 使用的 lint 检查：

```bash
flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics
```

新增命令时，在 `src/wocli/registry.py` 中注册 `COMMANDS` 和 `HELP_GROUPS`；命令实现放在 `src/wocli/commands/`。详细说明见 [docs/command-system.md](docs/command-system.md)。

## 贡献

欢迎提交 issue 和 pull request。提交前请运行测试和 lint 检查。

## 变更记录

版本变更见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT。见 [LICENSE](LICENSE)。
