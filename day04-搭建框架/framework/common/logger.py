# -*- coding: utf-8 -*-
"""
日志模块

为什么框架必须要有日志？
自动化最大的价值是"无人值守跑完还能定位问题"。
用例半夜挂了，第二天早上你只能看日志。没日志的框架等于白跑。
"""
import logging
import os
import sys
from datetime import datetime

# 日志目录：framework/logs/
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

_loggers = {}       # 缓存，避免重复创建 logger 导致日志重复打印


def get_logger(name="autotest"):
    """获取 logger（同一个 name 只会创建一次）"""
    if name in _loggers:
        return _loggers[name]

    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False      # 不往上传递，避免重复输出

    # 日志格式：时间 | 级别 | 文件名:行号 | 内容
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-5s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler：按天一个文件
    log_file = os.path.join(_LOG_DIR, f"{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _loggers[name] = logger
    return logger


if __name__ == "__main__":
    log = get_logger()
    log.info("这是一条 info 日志")
    log.warning("这是一条 warning 日志")
    log.error("这是一条 error 日志")
    print(f"日志文件位置：{_LOG_DIR}")
