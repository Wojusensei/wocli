# ```>_``` wocli

一个何意味终端工具箱，十分甚至是九分的好玩

我们支持 MacOS，Windows 和一部分 Linux 发行版的终端使用，但是由于某些特殊符号以及一些渲染问题。例如，目前发现在 Windows 系统上，非 Windows 11 用户在某些功能的使用体验上会受到影响，例如 ```wocli qr``` 这种包含特殊制表符的功能。

2026.08.03 以上问题得到了一定程度的修复，大幅提升了使用体验。

2026.08.04 进一步优化了此问题

2026.08.22 v0.4.0：修复干净安装缺少 colorama 依赖、Windows 下 sys/battery 数值错误、chat 十秒断线等问题，dino / badapple 命令正式注册

2026.08.22 v0.4.1：修复 dino 六个致命 bug（障碍不生成、生成即崩溃、跳跃不可玩等）实现完整可玩；badapple 帧序列改为首次自动下载并缓存，无需手动找文件

## 📦 安装

请先确保你装了python，然后执行：

```bash
pip install wocli
```

MacOS用户，如果终端提示 externally-managed-environment：

```bash
python3 -m venv wocli_env
source wocli_env/bin/activate
pip install wocli
```

Windows 用户如果被提示 wocli 命令找不到，请把 Python 的 Scripts 目录加到 PATH 环境变量。

如果你拉取到本地并对源代码进行了修改和调试，例如在本地用 ```pip install -e .``` 开发模式时，colorama 没自动装上是因为可编辑安装有时不会重新解析依赖，需要自行安装依赖

## 🔧 使用

直接输入 `wocli` 查看所有命令：

### 学习

wocli ip : 查看内网 IPv4 / IPv6、网关、公网 IP

wocli chat : 局域网聊天，不需要网络，输入对方 IP 即可对话；对方电脑运行此功能后会显示 IP 以及其他需要的信息

### 效率

wocli port : 查看当前端口占用情况

wocli tree : 树形显示当前文件夹结构，文件带大小

wocli sys : CPU / 内存 / 磁盘使用率，带动态进度条

wocli path : 列出 PATH 环境变量，标注缺失项

wocli battery : 电池信息，健康度评分

wocli wifi : WiFi 名称、信号强度打分、信道、加密方式


### 发电

wocli gpa ： 交互式算加权 GPA，附带毒舌点评

wocli luck ： 编程运势、幸运语言、bug 指数（每次输入指令都会重新抽，并不是每日固定）

wocli matrix 一段文本 另一段文本 其他文本（用空格划分）： 嘉豪数字雨，你输入的文本会出现在雨中。Ctrl+C 退出

wocli lolcat 文字 : 彩虹渐变色输出文字

wocli typing : 打字速度测试，给出 WPM 和评级

wocli progress : 假进度条动画，永远跑不完，Ctrl+C 退出

wocli qr 链接 : 终端生成可扫码的二维码

wocli goodbye : 花式退出动画，随机告别语

wocli cow 文字 : ASCII 牛说你说的话

wocli glitch 文字 : 文字故障风效果

wocli dead : 伪装终端死机，花屏、蓝屏、恢复

wocli dino : 终端跑酷小游戏，空格跳仙人掌、见高鸟别跳，自带最高分记录

wocli badapple : 播放 Bad Apple!! ASCII 动画（6572 帧），首次使用自动下载帧序列（约 4.6MB）并缓存到本地，之后离线播放；也可用 ```wocli badapple <帧目录/文件>``` 或环境变量 ```WOCLI_BADAPPLE_FRAMES``` 指定自备帧源


### coding

wocli time 文件 : 测试代码运行耗时

wocli hash 文件 : 计算文件 MD5 / SHA256

wocli regex '表达式' : 正则表达式测试器

## 🤝 贡献

欢迎每一位用户提交自己的奇思妙想，我会选取我能实现的(?)去实现。一些说明如下：

### issue

如果您在使用过程中发现 兼容性问题/功能与描述不符/可以优化的地方 ，请您尽情提交 issue ，就像在其他仓库那样

如果您在使用中有奇思妙想，例如 “这里明明可以做一个更好的功能！我要和窝居说一下···” ，您也可以专门为此提一个 issue 

### PR

在上面，某些 issue 虽然有很好的点子，但是受限于某些原因，可能没法及时更新出来。如果您是一位有热情投入这个仓库的开发者，欢迎前往未关闭的 issue 领取您的任务并在 修改/增添 某些功能后进行拉取请求，我会在审查并 merge 之后将新的版本提交至 PyPI 。

tips：

1,新的功能不仅需要单开一个模块，在模块顶端正确注释，还需要在 ```main.py``` 中进行正确注册，例如模块导入，```HELP_GROUPS```以及```COMMANDS```

2,```HELP_GROUPS```中对三个分类的要求并不严格，可以按照贡献者的想法将新功能分类，但是我不赞同将老功能的归类拆散。

3,请确保代码符合项目风格，仔细审查有无可以优化的逻辑，并在提交前运行检查确保新老功能均无异常。
