"""跨平台夹具测试的公共工具：伪造平台、伪造外部命令输出、伪造 /proc 文件.

这些采集函数都依赖各平台的命令输出，真机只有一台，
所以用"真实格式的输出"当夹具来覆盖其它平台的分支。
"""
import builtins
import io


def set_platform(monkeypatch, name):
    """把 platform.system() 固定成指定平台，用来跑特定平台的分支."""
    monkeypatch.setattr("platform.system", lambda: name)


def shim_run_cmd(monkeypatch, module, responses):
    """把模块里的 run_cmd 换成按关键字返回夹具输出的假实现.

    responses 是 (关键字, 输出) 列表，取第一个命中的关键字——
    关键字互相包含时（如 "iw" 与 "iwconfig"）要把更具体的写在前面。
    没命中的命令返回 None，等同于系统里没有这个工具。
    """
    def fake(cmd, timeout=6):
        joined = " ".join(cmd)
        for key, output in responses:
            if key in joined:
                return output
        return None
    monkeypatch.setattr(module, "run_cmd", fake)


def fake_files(monkeypatch, mapping):
    """把指定路径的 open 换成读内存字符串，用来伪造 /proc 下的文件."""
    real_open = builtins.open

    def patched(file, *args, **kwargs):
        if str(file) in mapping:
            return io.StringIO(mapping[str(file)])
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", patched)
