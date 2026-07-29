# wocli

一个何意味终端工具箱，十分甚至是九分的好玩

我们支持 macos 和 windows 的终端使用

## 安装

请先确保你装了python：

```bash
pip install wocli
```

如果终端提示 externally-managed-environment：

```bash
python3 -m venv wocli_env
source wocli_env/bin/activate
pip install wocli
```

Windows 用户如果被提示 wocli 命令找不到，请 Python 的 Scripts 目录加到 PATH 环境变量。

## 使用

直接输入 `wocli` 查看所有命令：

### 学习

wocli ip : 查看内网 IPv4 / IPv6、网关、公网 IP

wocli chat : 局域网聊天，不需要网络，输入对方 IP 即可对话

### 效率

wocli port : 查看当前端口占用情况

wocli tree : 树形显示当前文件夹结构，文件带大小

wocli sys : CPU / 内存 / 磁盘使用率，带动态进度条

wocli path : 列出 PATH 环境变量，标注缺失项

wocli battery : 电池信息，健康度评分

wocli wifi : WiFi 名称、信号强度打分、信道、加密方式


### 发电

wocli gpa ： 交互式算加权 GPA，附带毒舌点评

wocli luck ： 编程运势、幸运语言、bug 指数

wocli matrix ： 嘉豪数字雨，Ctrl+C 退出

wocli lolcat 文字 : 彩虹渐变色输出文字

wocli typing : 打字速度测试，给出 WPM 和评级

wocli progress : 假进度条动画，永远跑不完，Ctrl+C 退出

wocli qr 链接 : 终端生成可扫码的二维码

wocli goodbye : 花式退出动画，随机告别语

wocli cow 文字 : ASCII 牛说你说的话

wocli glitch 文字 : 文字故障风效果

wocli dead : 伪装终端死机，花屏、蓝屏、恢复


### coding

wocli time 文件 : 测试代码运行耗时

wocli hash 文件 : 计算文件 MD5 / SHA256

wocli regex '表达式' : 正则表达式测试器

## 贡献

欢迎每一位用户提交自己的奇思妙想，我会选取我能实现的(?)去实现。

我不能实现但是认为是智将的好点子会开 issue ，欢迎各位大手子领取 issue 并提交 PR ，我在确认合并之后会拉到本地重新上传 pypi 
