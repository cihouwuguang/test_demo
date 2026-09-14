# -*- coding: utf-8 -*-
"""
请求封装层 —— 整个框架的心脏

所有"统一处理"都收敛在这里：
  - 变量替换（${xxx}）
  - 拼完整 URL
  - 默认超时
  - 请求/响应日志
  - 异常处理
  - 失败重试（可选）

好处：要加"所有请求都带签名"这种需求，只改这一个文件。
"""
import os
import sys
import time

# 让本文件能直接运行做自测（python common/request_util.py）
#
# 为什么必须加这三行？
#   Python 直接运行脚本时，sys.path[0] 是「脚本所在目录」，也就是 common/，
#   而不是 framework/。所以 `from common.logger import ...` 找不到 common 包。
#   被 pytest / 被别的模块 import 时不会走这段，只有直接运行才补路径。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

from common.logger import get_logger
from common.var_pool import VarPool
from config.config import get_config


class RequestClient:
    """
    封装 requests.Session

    设计要点：
    1. 用 Session，自动维持 cookie、复用连接
    2. 默认超时从配置读，防止某个接口卡死拖垮全部
    3. 每个请求前后都打日志，方便回溯
    4. 变量替换在发送前统一做
    """

    def __init__(self, env=None):
        self.config = get_config(env)
        self.log = get_logger()
        self.session = requests.Session()

        # 统一设置默认请求头
        if self.config.headers:
            self.session.headers.update(self.config.headers)

        self.log.info(f"初始化 RequestClient：{self.config}")

    # ------------------------------------------------------------ 核心方法

    def send(self, method, path, retry=0, **kwargs):
        """
        发送请求

        :param method: GET / POST / PUT / DELETE
        :param path:   接口路径，如 /api/login
        :param retry:  失败重试次数
        :param kwargs: 其他 requests 参数（json/data/params/headers/timeout...）
        """
        # 1 变量替换：把 ${xxx} 换成真实值（path 和参数都可能带占位符）
        path = VarPool.replace(path)
        kwargs = VarPool.replace(kwargs)

        # 2 拼完整 URL
        url = self.config.base_url + path

        # 3 默认超时（用户显式传了就用用户的）
        kwargs.setdefault("timeout", self.config.timeout)

        # 4 发请求，带重试
        last_exc = None
        for attempt in range(retry + 1):
            self.log.info(f"请求 → {method.upper()} {url}")
            if kwargs.get("json"):
                self.log.info(f"       参数 {kwargs['json']}")
            if kwargs.get("params"):
                self.log.info(f"       query {kwargs['params']}")

            try:
                resp = self.session.request(method, url, **kwargs)
                self.log.info(f"响应 ← {resp.status_code}（耗时 {resp.elapsed.total_seconds():.3f}s）")
                self.log.info(f"       {resp.text[:500]}")
                return resp

            except requests.exceptions.Timeout as e:
                last_exc = e
                self.log.warning(f"第 {attempt + 1} 次请求超时：{e}")
            except requests.exceptions.ConnectionError as e:
                last_exc = e
                self.log.warning(f"第 {attempt + 1} 次连接失败：{e}")
            except requests.exceptions.RequestException as e:
                last_exc = e
                self.log.error(f"请求异常：{type(e).__name__} - {e}")
                raise        # 非超时/连接类异常，直接抛出，不重试

            if attempt < retry:
                time.sleep(1)

        # retry=0 时说「重试 0 次」很怪，这里分开措辞
        tip = f"重试 {retry} 次后仍然失败" if retry else "请求失败"
        raise TimeoutError(f"{tip}：{last_exc}")

    # ------------------------------------------------------------ 便捷方法

    def get(self, path, **kwargs):
        return self.send("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.send("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.send("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.send("DELETE", path, **kwargs)

    # ------------------------------------------------------------ 其他

    def set_header(self, key, value):
        """设置全局请求头（比如登录后设置 token）"""
        self.session.headers[key] = value
        self.log.info(f"设置全局请求头：{key} = {str(value)[:20]}...")

    def close(self):
        self.session.close()
        self.log.info("关闭 Session")


# ---------------------------------------------------------------- 单例

_client = None


def get_client(env=None):
    """
    获取全局唯一的 client（session 级共享，避免重复登录）

    conftest.py 的 client fixture 也走这个函数，
    目的是让「fixture 拿到的 client」和「业务类里 get_client() 拿到的 client」
    是同一个对象。否则会出现两份 client：一份登录过、一份没登录，
    后面忘传 client 的用例就莫名其妙 401。
    """
    global _client
    if _client is None:
        _client = RequestClient(env)
    return _client


def reset_client():
    """关掉并丢弃单例（一次测试跑完时调用，避免下次拿到已关闭的 Session）"""
    global _client
    if _client is not None:
        try:
            _client.close()
        finally:
            _client = None


if __name__ == "__main__":
    c = RequestClient()
    r = c.post("/api/login", json={"username": "admin", "password": "123456"})
    print(r.json())
    c.close()
