# -*- coding: utf-8 -*-
"""
业务层父类

所有业务 API 类都继承它，公共能力只在这里写一次。
这就是 Day 1 讲的"继承"在框架里的实际用法。
"""
from common.logger import get_logger
from common.request_util import get_client


class BaseAPI:
    """
    业务 API 的父类

    子类只需要：
      1. 定义自己的接口方法
      2. 只关心路径和业务参数

    公共的（日志、超时、变量替换、异常处理）全在 RequestClient 里，这里不管。
    """

    def __init__(self, client=None):
        self.client = client or get_client()
        self.log = get_logger()

    @property
    def base_url(self):
        return self.client.config.base_url
