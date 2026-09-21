# -*- coding: utf-8 -*-
"""
断言封装

设计原则（比"封装得好不好看"重要得多）：
    **宁可报错，也不要假绿。**

一次错误的输入、一次字段名拼错，都不应该换来一条绿色的 passed。
所以这个模块在下面这些情况下会主动报错，而不是"算通过"：

  1. 断言列表是空的            → 报错（零断言无法证明任何事）
  2. JSONPath 没匹配到任何东西  → 报错（和「值为 null」严格区分）
  3. 响应体不是合法 JSON        → 干净的断言失败（不是 JSONDecodeError）
  4. 算子参数个数不对          → 报错（多传的参数不会被静默忽略）

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


# ---------------------------------------------------------------- 哨兵值

class _NotFound:
    """
    JSONPath「没匹配到任何东西」的哨兵值

    为什么必须有这个东西？
      如果取不到值就返回 None，就和「字段存在、值就是 null」完全无法区分。后果：

        is_null: ["$.data.non_exist_field"]   → 断言"为空"成功了，
          可那个字段压根不存在，其实是路径写错了；
        ne: ["$.data.tokenn", "some_value"]   → None != "some_value" → 恒真通过，
          比零断言更隐蔽。

      所以「未匹配」必须是独立于 None 的一种值，让上层能把它当成错误处理。
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "<JSONPath 未匹配>"

    def __bool__(self):
        return False


NOT_FOUND = _NotFound()


# ---------------------------------------------------------------- 取值

def parse_json(resp):
    """
    解析响应体 JSON，失败时给**干净的断言失败**，而不是抛 JSONDecodeError

    为什么重要：服务端返回 500 + 一整页 HTML 错误页时，
    直接 resp.json() 会抛 JSONDecodeError ——
    排查的人会以为"框架坏了 / 断言语法写错了"，
    而真相是"被测服务 500 了"。

    把"用户用错了"和"框架坏了"区分开，是框架的基本素养。
    """
    try:
        return resp.json()
    except ValueError:          # requests 抛的 json.JSONDecodeError 继承自 ValueError
        raise AssertionError(
            f"响应不是合法 JSON，无法按 JSONPath 取值。"
            f"HTTP {resp.status_code}，"
            f"Content-Type={resp.headers.get('Content-Type')!r}，"
            f"body 前 200 字符：{resp.text[:200]!r}"
        )


def extract_by_jsonpath(data, expr):
    """
    按 JSONPath 从响应里取值

    :param data: 已转成 dict 的响应体
    :param expr: 如 $.data.token
    :return:
        匹配到 1 个  → 返回那个真实值（可能就是 None）
        匹配到多个  → 返回值的列表，如 $.data.list[*] → [1, 2, 3]
        一个都没匹配到 → 返回 NOT_FOUND 哨兵（**不是 None**）
    """
    matches = parse(expr).find(data)
    if not matches:
        return NOT_FOUND
    if len(matches) == 1:
        return matches[0].value
    return [m.value for m in matches]


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
            return extract_by_jsonpath(parse_json(resp), expr)
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
    """is_null 只要 1 个参数：实际值表达式"""
    assert actual is None, f"断言失败[为空]：实际 {actual!r}。{msg}"


def assert_not_null(actual, expected=None, msg=""):
    """not_null 只要 1 个参数：实际值表达式"""
    assert actual is not None, f"断言失败[不为空]：实际是 None。{msg}"


def assert_approx(actual, expected, msg="", tolerance=0.01):
    """
    近似相等 —— 专门给金额这类浮点数用

    为什么不直接用 eq？
        0.1 + 0.2 == 0.3  →  False
        二进制浮点数无法精确表示十进制小数，金额用 == 比较迟早会翻车。
        （这也是项目自己在面试题里强调的点，断言算子必须配套提供。）
    """
    delta = abs(actual - expected)
    assert delta < tolerance, \
        f"断言失败[近似相等]：期望 {expected!r}（容差 {tolerance}），" \
        f"实际 {actual!r}，差值 {delta}。{msg}"


ASSERT_MAP = {
    "eq": assert_eq,
    "ne": assert_ne,
    "contains": assert_contains,
    "not_contains": assert_not_contains,
    "gt": assert_gt,
    "lt": assert_lt,
    "is_null": assert_is_null,
    "not_null": assert_not_null,
    "approx": assert_approx,
}

# 每个算子需要几个参数 —— 用来拦住「多传/少传参数被静默忽略」
ASSERT_ARITY = {
    "eq": 2,
    "ne": 2,
    "contains": 2,
    "not_contains": 2,
    "gt": 2,
    "lt": 2,
    "is_null": 1,
    "not_null": 1,
    "approx": 2,
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
        raise ValueError(
            f"用例【{case_name}】没有任何断言（validate 为空）。\n"
            "零断言的用例什么也证明不了，框架不会让它「通过」。\n"
            "请补上 validate 字段，例如：\n"
            "    validate:\n"
            "      - eq: [status_code, 200]\n"
            "      - eq: [$.code, 0]"
        )

    for item in validate_list:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError(
                f"用例【{case_name}】的断言格式错误：应为只含一个算子的字典，"
                f"实际：{item!r}"
            )

        for op, args in item.items():
            if op not in ASSERT_MAP:
                raise ValueError(
                    f"用例【{case_name}】不支持的断言方式：{op}，"
                    f"可选：{sorted(ASSERT_MAP.keys())}"
                )

            if not isinstance(args, (list, tuple)) or len(args) < 1:
                raise ValueError(
                    f"用例【{case_name}】断言 {op} 的参数格式应为 "
                    f"[实际值表达式, 期望值]，实际：{args!r}"
                )

            # 参数个数校验：多传的参数不会被静默忽略，而是直接报错
            expect_arity = ASSERT_ARITY[op]
            if len(args) != expect_arity:
                hint = ""
                if op in ("is_null", "not_null"):
                    hint = (f"\n  {op} 只接受 1 个参数（实际值表达式），"
                            "不需要写期望值。")
                raise ValueError(
                    f"用例【{case_name}】断言 {op} 需要 {expect_arity} 个参数，"
                    f"实际给了 {len(args)} 个：{args!r}。{hint}"
                )

            actual_expr = args[0]
            expected = args[1] if len(args) > 1 else None
            actual = _resolve(resp, actual_expr)
            msg = f"用例【{case_name}】 表达式 {actual_expr}"

            # 「路径没匹配到」必须当错误处理，不能当成 None 参与比较
            if actual is NOT_FOUND:
                raise AssertionError(
                    f"断言失败[路径未匹配]：{msg}\n"
                    f"  JSONPath 在响应里没有匹配到任何值 —— 字段不存在，"
                    f"或者路径写错了。\n"
                    f"  注意这和「字段存在、值为 null」是两回事："
                    f"前者是断言写错，后者才是业务事实。\n"
                    f"  响应体前 200 字符：{resp.text[:200]!r}"
                )

            ASSERT_MAP[op](actual, expected, msg)


if __name__ == "__main__":
    # 自测块用 assert，不用 print —— 输出要"看着对"是假绿的第一步
    data = {"code": 0, "data": {"token": "abc", "list": [1, 2, 3], "nil": None}}

    assert extract_by_jsonpath(data, "$.data.token") == "abc"
    assert extract_by_jsonpath(data, "$.data.list[*]") == [1, 2, 3]
    assert extract_by_jsonpath(data, "$.data.not_exist") is NOT_FOUND
    assert extract_by_jsonpath(data, "$.data.nil") is None      # 存在但为 null
    assert extract_by_jsonpath(data, "$.data.not_exist") is not None

    assert_approx(0.1 + 0.2, 0.3)
    try:
        assert_eq(0.1 + 0.2, 0.3)
        raise SystemExit("0.1+0.2 竟然等于 0.3？浮点语义变了，请复核")
    except AssertionError:
        pass

    print("assert_util 自测通过：取值语义、未匹配哨兵、近似比较均符合预期")
