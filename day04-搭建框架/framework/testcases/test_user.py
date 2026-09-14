# -*- coding: utf-8 -*-
"""
用户模块用例（数据驱动）
"""
import os

import pytest

from common.case_runner import run_case
from common.yaml_util import read_yaml

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "test_user.yaml")
CASES = read_yaml(_DATA_FILE)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_user(client, case):
    run_case(client, case)
