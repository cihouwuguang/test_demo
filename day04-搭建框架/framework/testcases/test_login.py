# -*- coding: utf-8 -*-
"""
登录模块用例（数据驱动）

整个文件没有写任何请求细节 —— 全部来自 data/test_login.yaml
加用例只改 YAML，不用动这个文件
"""
import os

import pytest

from common.case_runner import load_cases, run_case

# 读用例数据 —— 用 load_cases 而不是 read_yaml：
# 它在导入时就把每条用例的结构校验一遍，字段拼错会在"收集用例"阶段直接报错，
# 而不是变成一条静默通过的绿用例
_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "test_login.yaml")
CASES = load_cases(_DATA_FILE)


@pytest.mark.smoke
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_login(client, case):
    """
    client 是 conftest.py 提供的 session 级 fixture（已登录）
    case  是 YAML 里的一条数据
    """
    run_case(client, case)
