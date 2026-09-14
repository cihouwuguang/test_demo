# -*- coding: utf-8 -*-
"""
用例执行引擎 —— 数据驱动的核心

一条 YAML 用例长这样：
    name: 登录成功
    request:
      method: POST
      path: /api/login
      json:
        username: admin
        password: "123456"
    extract:
      token: $.data.token        # 提取出来给后面的用例用
    validate:
      - eq: [$.code, 0]
      - eq: [$.data.username, admin]

run_case 负责：发请求 → 提取变量 → 执行断言

正因为有了这个引擎，"加一条用例"变成"往 YAML 里加一段"，不用写 Python 代码。
"""
import copy

from common.assert_util import do_validate, extract_by_jsonpath
from common.logger import get_logger
from common.var_pool import VarPool

log = get_logger()


def run_case(client, case):
    """
    执行一条用例

    :param client: RequestClient 实例
    :param case:   用例字典（从 YAML 读出来的）
    :return:       响应对象
    """
    name = case.get("name", "未命名用例")
    log.info(f"{'=' * 50}")
    log.info(f"开始执行用例：{name}")

    # 0 先整体做一次变量替换
    #    这样 path、请求参数、断言期望值里的 ${xxx} 都会被换成真实值
    case = VarPool.replace(case)

    # 1 发请求（用 copy 避免 pop 改动原始数据）
    req = copy.deepcopy(case.get("request", {}))
    method = req.pop("method")
    path = req.pop("path")

    if not method or not path:
        raise ValueError(f"用例【{name}】缺少 method 或 path")

    resp = client.send(method, path, **req)

    # 2 提取变量（给下游用例用）
    for var_name, expr in case.get("extract", {}).items():
        value = extract_by_jsonpath(resp.json(), expr)
        if value is None:
            log.warning(f"提取失败：{expr} 在响应中不存在，变量 {var_name} 未设置")
        else:
            VarPool.set(var_name, value)
            log.info(f"提取变量：{var_name} = {value}")

    # 3 执行断言
    do_validate(resp, case.get("validate", []), case_name=name)

    log.info(f"用例执行通过：{name}")
    return resp


def run_cases(client, cases):
    """批量执行（一般不用，pytest 的 parametrize 已经帮我们做了）"""
    for case in cases:
        run_case(client, case)
