# -*- coding: utf-8 -*-
"""
订单模块用例（数据驱动）

这里的用例演示了完整的接口依赖链：
  创建订单 → extract order_id → 查订单/支付 → 用 ${order_id}
"""
import os

import pytest

from common.case_runner import run_case
from common.yaml_util import read_yaml

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "test_order.yaml")
CASES = read_yaml(_DATA_FILE)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_order(client, case):
    run_case(client, case)
