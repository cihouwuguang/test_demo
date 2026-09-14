# -*- coding: utf-8 -*-
"""
断言封装

为什么不用裸 assert？
裸 assert 失败时只告诉你"不相等"，不告诉你是谁和谁不相等。
封装后失败信息自带上下文，排查效率差很多。

支持的断言方式：
  eq            相等
  ne            不等
  contains      包含（字符串子串 / 列表成员 / 字典 key）
  not_contains  不包含
  gt / lt       大于 / 小于
  is_null       为空
  not_null      不为空
"""
from jsonpath_ng import parse


# ---------------------------------------------------------------- 取值

def extract_by_jsonpath(data, expr):
    """
    按 JSONPath 从响应里取值，取不到返回 None（不抛异常）

    :param data: 已转成 dict 的响应体
    :param expr: 如 $.data.token
    """
    matches = parse(expr).find(data)
    return matches[0].value if matches else None


def _resolve(resp, expr):
    """
    把用例里写的表达式解析成实际值

    $.code        → 从响应 JSON 里取
    status_code   → HTTP 状态码
    其他          → 当字面量
    """
    if isinstance(expr, str):
        if expr == "status_code":
            return resp.status_code
        if expr.startswith("$"):
            return extract_by_jsonpath(resp.json(), expr)
    return expr


# ---------------------------------------------------------------- 断言方法

def assert_eq(actual, expected, msg=""):
    assert actual == expected, \
        f"断言失败[相等]：期望 {expected!r}，实际 {actual!r}。{msg}"


def assert_ne(actual, expected, msg=""):
    assert actual != expected, \
        f"断言失败[不等]：不应等于 {expected!r}。{msg}"


def assert_contains(actual, expected, msg=""):
    assert expected in actual, \
        f"断言失败[包含]：{actual!r} 中不包含 {expected!r}。{msg}"


def assert_not_contains(actual, expected, msg=""):
    assert expected not in actual, \
        f"断言失败[不包含]：{actual!r} 中包含了 {expected!r}。{msg}"


def assert_gt(actual, expected, msg=""):
    assert actual > expected, \
        f"断言失败[大于]：期望 {actual!r} > {expected!r}。{msg}"


def assert_lt(actual, expected, msg=""):
    assert actual < expected, \
        f"断言失败[小于]：期望 {actual!r} < {expected!r}。{msg}"


def assert_is_null(actual, expected=None, msg=""):
    """expected 参数用不到，保留是为了和其他断言函数签名一致"""
    assert actual is None, f"断言失败[为空]：实际 {actual!r}。{msg}"


def assert_not_null(actual, expected=None, msg=""):
    """expected 参数用不到，保留是为了和其他断言函数签名一致"""
    assert actual is not None, f"断言失败[不为空]：实际是 None。{msg}"


ASSERT_MAP = {
    "eq": assert_eq,
    "ne": assert_ne,
    "contains": assert_contains,
    "not_contains": assert_not_contains,
    "gt": assert_gt,
    "lt": assert_lt,
    "is_null": assert_is_null,
    "not_null": assert_not_null,
}


# ---------------------------------------------------------------- 执行断言

def do_validate(resp, validate_list, case_name=""):
    """
    按顺序执行断言列表

    :param resp:          响应对象
    :param validate_list: 形如 [{"eq": ["$.code", 0]}, {"contains": ["$.msg", "success"]}]
    :param case_name:     用例名，用于失败信息
    """
    if not validate_list:
        return

    for item in validate_list:
        for op, args in item.items():
            if op not in ASSERT_MAP:
                raise ValueError(f"不支持的断言方式：{op}，可选：{list(ASSERT_MAP.keys())}")

            if not isinstance(args, (list, tuple)) or len(args) < 1:
                raise ValueError(f"断言 {op} 的参数格式应为 [实际值表达式, 期望值]，实际：{args}")

            # is_null / not_null 只需要一个参数
            actual_expr = args[0]
            expected = args[1] if len(args) > 1 else None
            actual = _resolve(resp, actual_expr)
            msg = f"用例【{case_name}】 表达式 {actual_expr}"
            ASSERT_MAP[op](actual, expected, msg)


if __name__ == "__main__":
    data = {"code": 0, "data": {"token": "abc", "list": [1, 2, 3]}}
    print(extract_by_jsonpath(data, "$.data.token"))       # abc
    print(extract_by_jsonpath(data, "$.data.not_exist"))   # None
    print(extract_by_jsonpath(data, "$.data.list[*]"))     # [1, 2, 3]
