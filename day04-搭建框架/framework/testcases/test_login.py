# -*- coding: utf-8 -*-
"""
登录模块用例（数据驱动）

整个文件没有写任何请求细节 —— 全部来自 data/test_login.yaml
加用例只改 YAML，不用动这个文件
"""
import os

import pytest

from common.case_runner import run_case
from common.yaml_util import read_yaml

# 读用例数据
_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "test_login.yaml")
CASES = read_yaml(_DATA_FILE)


@pytest.mark.smoke
@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_login(client, case):
    """
    client 是 conftest.py 提供的 session 级 fixture（已登录）
    case  是 YAML 里的一条数据
    """
    run_case(client, case)
