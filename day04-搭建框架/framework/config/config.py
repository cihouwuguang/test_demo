# -*- coding: utf-8 -*-
"""
配置读取

为什么要有这一层？
环境地址散落在用例里是最常见的坏味道——换个环境要改几十处。
抽出来之后：换环境只改 config.yaml（或命令行 --env=prod）。
"""
import os
import sys

# 让本文件能直接运行做自测（python config/config.py）
# 直接运行时 sys.path[0] 是 config/，找不到 common 包，这里手动补上 framework 根目录
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.yaml_util import read_yaml

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

_current_env = None       # 由命令行 --env 或 set_env() 指定


class EnvConfig:
    """一个环境的配置"""

    def __init__(self, env_name, conf):
        self.env_name = env_name
        self.base_url = conf["base_url"]
        self.timeout = conf.get("timeout", 10)
        self.headers = conf.get("headers", {})

    def __repr__(self):
        return (f"EnvConfig(env={self.env_name}, base_url={self.base_url}, "
                f"timeout={self.timeout})")


def set_env(env):
    """切换环境（供命令行参数调用）"""
    global _current_env
    _current_env = env


def get_config(env=None):
    """
    获取配置

    优先级：显式传参 > 命令行 --env > config.yaml 的 default_env
    """
    raw = read_yaml(_CONFIG_PATH)
    name = env or _current_env or raw.get("default_env", "test")

    if name not in raw:
        raise KeyError(f"配置里没有环境 {name}，可选：{[k for k in raw if k != 'default_env']}")

    return EnvConfig(name, raw[name])


if __name__ == "__main__":
    print(get_config())
    print(get_config("prod"))
