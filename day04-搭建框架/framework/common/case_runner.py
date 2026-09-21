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
      - eq: [status_code, 200]
      - eq: [$.code, 0]

run_case 负责：校验用例结构 → 发请求 → 提取变量 → 执行断言

正因为有了这个引擎，"加一条用例"变成"往 YAML 里加一段"，不用写 Python 代码。

[!] 但也正因为自由度这么高，**必须有 schema 校验兜底**，否则：
    漏写 validate、把 validate 拼成 validates、字段名写错一个字，
    都会变成"零断言执行 + 一条绿色的 passed"。
    详见 validate_case() 的注释。
"""
import copy

from common.assert_util import (NOT_FOUND, do_validate, extract_by_jsonpath,
                                parse_json)
from common.logger import get_logger
from common.var_pool import VarPool

log = get_logger()

# 一条用例允许出现的字段。多出来的字段一律报错，不做静默忽略。
ALLOWED_CASE_KEYS = ("name", "request", "extract", "validate")


# ---------------------------------------------------------------- 用例结构校验

def validate_case(case, index=None):
    """
    校验用例结构 —— 缺字段、字段名拼错，必须在这里报错

    为什么这一步不能省？
      本框架的卖点是"加用例只改 YAML，不用写代码"，自由度很高。
      而**自由度没有 schema 兜底，就是假绿的温床**：

        A. 用例完全没有 validate 字段
           → case.get("validate", []) 取到空列表 → 零断言 → 照常打日志"用例执行通过"
        B. 字段名拼成 validates（一个字母的差别）
           → 同上。哪怕请求参数是故意写错的、业务上必然失败，
             在报告里依然是一条绿色的 passed

      场景 B 最危险：它比"用例失败"糟糕得多，因为没有任何人会去看它。

    :return: 用例名（已做兜底）
    """
    where = f"第 {index} 条用例" if index is not None else "用例"

    if not isinstance(case, dict):
        raise ValueError(f"{where}格式错误：应该是字典，实际是 {type(case).__name__}：{case!r}")

    name = case.get("name") or f"未命名用例（{where}）"

    # 1 未知字段（拼错的字段名会在这里被抓住）
    unknown = [k for k in case if k not in ALLOWED_CASE_KEYS]
    if unknown:
        raise ValueError(
            f"用例【{name}】出现未知字段：{unknown}\n"
            f"  允许的字段只有：{list(ALLOWED_CASE_KEYS)}\n"
            f"  拼错的字段不会被使用，也不会报错——所以这里必须拦下来。\n"
            f"  最常见的拼错：validates / validate_list / request_body"
        )

    # 2 必填字段
    for field in ("name", "request", "validate"):
        if field not in case:
            raise ValueError(
                f"用例【{name}】缺少必填字段「{field}」。\n"
                f"  一条用例必须包含：{list(ALLOWED_CASE_KEYS)}\n"
                f"  （extract 是可选的）"
            )

    # 3 request 结构
    req = case["request"]
    if not isinstance(req, dict):
        raise ValueError(f"用例【{name}】的 request 应该是字典，实际：{req!r}")
    for key in ("method", "path"):
        if not req.get(key):
            raise ValueError(f"用例【{name}】的 request 缺少 {key}，实际：{req!r}")

    # 4 extract 结构（可选，但写了就得是字典）
    extract = case.get("extract")
    if extract is not None and not isinstance(extract, dict):
        raise ValueError(f"用例【{name}】的 extract 应该是字典，实际：{extract!r}")

    # 5 validate 必须是非空列表
    validate = case["validate"]
    if not isinstance(validate, list) or not validate:
        raise ValueError(
            f"用例【{name}】的 validate 必须是非空列表，当前是 {validate!r}。\n"
            "  没有断言的用例证明不了任何东西，框架不会让它「通过」。\n"
            "  如果这条用例暂时不需要断言，请先删掉它，不要留着占位。"
        )

    return name


def load_cases(path):
    """
    读 YAML 用例文件并**整体校验**

    建议用例文件在收集阶段就调用它，这样字段拼错会在"收集用例"时就报出来，
    而不是等到某条用例跑了一半才炸。
    """
    from common.yaml_util import read_yaml

    cases = read_yaml(path)
    if not isinstance(cases, list):
        raise ValueError(f"用例文件 {path} 的顶层应该是列表，实际是 {type(cases).__name__}")
    for i, case in enumerate(cases, start=1):
        validate_case(case, index=i)
    return cases


# ---------------------------------------------------------------- 执行

def run_case(client, case):
    """
    执行一条用例

    :param client: RequestClient 实例
    :param case:   用例字典（从 YAML 读出来的）
    :return:       响应对象
    """
    # 0 校验结构 —— 必须在最前面。零断言/字段拼错的用例绝不放过
    name = validate_case(case)

    log.info(f"{'=' * 50}")
    log.info(f"开始执行用例：{name}")

    # 1 整体做一次变量替换
    #    这样 path、请求参数、断言期望值里的 ${xxx} 都会被换成真实值
    case = VarPool.replace(case)

    # 2 发请求（用 copy 避免 pop 改动原始数据）
    req = copy.deepcopy(case["request"])
    method = req.pop("method")
    path = req.pop("path")

    resp = client.send(method, path, **req)

    # 3 提取变量（给下游用例用）
    #
    #    提取失败必须直接判用例失败。
    #    只打一条 WARNING 然后继续，会让错误"跑到下游才炸"：
    #      上游用例字段名写错、没提到值 → 它自己是绿的；
    #      下游用例报 KeyError: 变量 ${order_id} 不在变量池中
    #      → 报错位置指向受害者，不指向肇因，排查时间翻几倍。
    for var_name, expr in case.get("extract", {}).items():
        value = extract_by_jsonpath(parse_json(resp), expr)

        if value is NOT_FOUND:
            raise AssertionError(
                f"用例【{name}】提取变量失败：{var_name} = {expr}\n"
                f"  JSONPath 在响应里没有匹配到任何值（字段不存在或路径写错）。\n"
                f"  提取不出值说明这条用例的前置没满足，它不该被判通过——\n"
                f"  否则下游用例会拿著空变量池报一个指向错误位置的 KeyError。\n"
                f"  响应体前 200 字符：{resp.text[:200]!r}"
            )
        if value is None:
            raise AssertionError(
                f"用例【{name}】提取变量失败：{var_name} = {expr}\n"
                f"  字段存在，但值是 null，无法作为变量传给下游用例。\n"
                f"  响应体前 200 字符：{resp.text[:200]!r}"
            )

        VarPool.set(var_name, value)
        log.info(f"提取变量：{var_name} = {value}")

    # 4 执行断言（validate 非空已在上面的结构校验里保证）
    do_validate(resp, case["validate"], case_name=name)

    log.info(f"用例执行通过：{name}")
    return resp


def run_cases(client, cases):
    """批量执行（一般不用，pytest 的 parametrize 已经帮我们做了）"""
    for case in cases:
        run_case(client, case)
