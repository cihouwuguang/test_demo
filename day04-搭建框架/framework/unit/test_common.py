# -*- coding: utf-8 -*-
"""
common 层纯函数的单元测试

为什么这个目录必须存在？
  这一套课程的主题是"怎么测"，而 common/ 下的东西全是**最适合被单测的纯函数**：
  变量替换、JSONPath 取值、断言算子、用例结构校验。
  之前它们的自测块全是 print —— 输出对不对要靠眼睛看，等于没有回归。
  一个教测试的项目，自己不做单元测试，说服力直接归零。

这些测试**不需要 mock 服务**，可以单独跑：

    cd day04-搭建框架/framework
    pytest unit/ -v

它们守的不是"功能有没有"，而是**框架的假绿路径有没有被重新打开**：
  - 零断言的用例还能不能静默通过？
  - 路径写错还能不能"恰好"断言成功？
  - 服务端 500 吐 HTML 时，报错是"框架崩了"还是"断言失败"？
"""
import json
import os
import sys

import pytest

# 让 unit/ 下的测试也能 import common / config
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.assert_util import (NOT_FOUND, assert_approx, do_validate,          # noqa: E402
                               extract_by_jsonpath, parse_json)
from common.case_runner import load_cases, validate_case                       # noqa: E402
from common.var_pool import VarPool                                            # noqa: E402
from config.config import get_config                                           # noqa: E402


class FakeResp:
    """最小可用的响应替身，用来构造各种"服务端不乖"的场景"""

    def __init__(self, status_code=200, body=None, raw_text=None, headers=None):
        self.status_code = status_code
        self._body = body
        self._raw_text = raw_text
        self.headers = headers or {"Content-Type": "application/json"}

    @property
    def text(self):
        if self._raw_text is not None:
            return self._raw_text
        return json.dumps(self._body, ensure_ascii=False)

    def json(self):
        if self._raw_text is not None:
            # 模拟 requests 在响应不是 JSON 时的行为
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._body


@pytest.fixture(autouse=True)
def isolated_var_pool():
    """
    变量池是类变量（全局单例），单测里会往里塞一堆值。

    这里用「**快照 + 还原**」，而不是直接 `VarPool.clear()`。
    为什么？因为 `clear()` 会把接口用例依赖的全局变量（`test_user_id`、
    `token`）一起擦掉：

      · 单独跑 `pytest unit/` 看不出来；
      · 但 `pytest unit/ testcases/` 这样显式指定顺序，
        或者并发时 `-n 2 --dist=loadscope` 把 unit 和 testcases 分到同一个进程，
        接口用例就会因为"变量池里没有 test_user_id"而失败 ——
        而报错位置指向接口用例，真正的肇因却在单测的清理动作里。

    教训很通用：**碰全局状态时要"用完还原"，不要"直接清空"。**
    """
    saved = VarPool.all()
    VarPool.clear()
    yield
    VarPool.clear()
    for key, value in saved.items():
        VarPool.set(key, value)


# ================================================================ 变量池

class TestVarPool:

    def test_整串占位符保留原类型(self):
        """这是课程里反复强调的坑：int 不能变成 str"""
        VarPool.set("user_id", 5)
        assert VarPool.replace({"userId": "${user_id}"}) == {"userId": 5}
        assert isinstance(VarPool.replace("${user_id}"), int)

    def test_部分占位符转成字符串拼接(self):
        VarPool.set("user_id", 5)
        assert VarPool.replace({"desc": "订单${user_id}号"}) == {"desc": "订单5号"}

    def test_嵌套结构递归替换(self):
        VarPool.set("a", 1)
        VarPool.set("b", "x")
        data = {"list": [{"k": "${a}"}, "前缀${b}后缀"], "n": 3}
        assert VarPool.replace(data) == {"list": [{"k": 1}, "前缀x后缀"], "n": 3}

    def test_非字符串原样返回(self):
        assert VarPool.replace(3.14) == 3.14
        assert VarPool.replace(None) is None
        assert VarPool.replace(True) is True

    def test_引用不存在的变量必须抛KeyError(self):
        """静默替换失败 = 用例带着错误的参数发出去，比直接报错危险得多"""
        with pytest.raises(KeyError) as e:
            VarPool.replace({"x": "${not_set}"})
        assert "not_set" in str(e.value)

    def test_get默认值(self):
        assert VarPool.get("nope") is None
        assert VarPool.get("nope", "d") == "d"

    def test_隔离fixture是快照还原而不是清空(self):
        """
        回归测试：unit/ 的 autouse 隔离 fixture 必须"用完还原"。

        为什么值得单独测？因为它一旦被改回 VarPool.clear()，
        接口用例会在这些场景下莫名其妙地挂：
          · pytest unit/ testcases/（显式指定顺序，单测先跑）
          · pytest -n 2 --dist=loadscope（unit 和 testcases 落同一个进程）
        而报错位置指向接口用例，真正的肇因却在这个 fixture 里。

        这里直接驱动 fixture 生成器来验证语义，不依赖执行顺序。
        """
        VarPool.set("接口用例依赖的变量", "keep-me")

        gen = isolated_var_pool.__wrapped__()      # 取 autouse fixture 的原始生成器
        next(gen)                                  # 进入：快照 + 清空
        assert VarPool.get("接口用例依赖的变量") is None, "进入时应该清空，保证单测互不干扰"

        VarPool.set("单测自己的变量", 1)            # 模拟单测往池子里写东西

        with pytest.raises(StopIteration):
            next(gen)                              # 退出：还原

        assert VarPool.get("接口用例依赖的变量") == "keep-me", \
            "退出时必须还原——否则会擦掉接口用例依赖的 test_user_id / token"
        assert VarPool.get("单测自己的变量") is None, "单测自己写的东西不该泄漏出去"


# ================================================================ JSONPath 取值

class TestExtractByJsonpath:

    data = {"code": 0, "data": {"token": "abc", "list": [1, 2, 3], "nil": None}}

    def test_匹配到单值(self):
        assert extract_by_jsonpath(self.data, "$.data.token") == "abc"

    def test_匹配到多个值返回列表(self):
        assert extract_by_jsonpath(self.data, "$.data.list[*]") == [1, 2, 3]

    def test_字段存在但值为null返回None(self):
        assert extract_by_jsonpath(self.data, "$.data.nil") is None

    def test_字段不存在返回哨兵而不是None(self):
        """
        这条是整个 assert_util 最关键的设计：
        「未匹配」和「值为 null」必须能区分开，否则
          is_null 打在不存在字段上会"通过"
          ne 配错路径会恒真通过
        """
        result = extract_by_jsonpath(self.data, "$.data.not_exist")
        assert result is NOT_FOUND
        assert result is not None

    def test_哨兵可被布尔判断为假(self):
        assert not extract_by_jsonpath(self.data, "$.data.not_exist")


# ================================================================ 响应解析

class TestParseJson:

    def test_正常JSON(self):
        assert parse_json(FakeResp(body={"code": 0})) == {"code": 0}

    def test_非JSON响应给出干净报错(self):
        """
        服务端 500 吐 HTML 时，必须报"响应不是合法 JSON"，而不是抛
        JSONDecodeError —— 后者会让人以为"框架坏了 / 断言语法写错了"，
        而真相是被测服务挂了。
        """
        resp = FakeResp(status_code=500, raw_text="<html>500 error</html>",
                        headers={"Content-Type": "text/html"})
        with pytest.raises(AssertionError) as e:
            parse_json(resp)
        msg = str(e.value)
        assert "不是合法 JSON" in msg
        assert "500" in msg


# ================================================================ 断言算子

class TestAssertOps:

    def test_近似比较可以容纳浮点误差(self):
        assert_approx(0.1 + 0.2, 0.3)          # 精确比较会失败的那种

    def test_近似比较超出容差要失败(self):
        with pytest.raises(AssertionError):
            assert_approx(99.9, 100.9)

    @pytest.mark.parametrize("op,args,actual_expr", [
        ("eq", [0], "$.code"),
        ("ne", [1], "$.code"),
        ("contains", ["success"], "$.msg"),
        ("not_contains", ["failed"], "$.msg"),
        ("gt", [-1], "$.code"),
        ("lt", [1], "$.code"),
        ("not_null", [], "$.msg"),
        ("approx", [0.0], "$.code"),
    ])
    def test_所有算子都能正常通过(self, op, args, actual_expr):
        resp = FakeResp(body={"code": 0, "msg": "success"})
        do_validate(resp, [{op: [actual_expr] + args}], case_name=f"{op} 正常")

    def test_is_null能正确判断null(self):
        resp = FakeResp(body={"code": 0, "data": {"x": None}})
        do_validate(resp, [{"is_null": ["$.data.x"]}], case_name="is_null 正常")

    def test_eq失败时要带上上下文(self):
        resp = FakeResp(body={"code": 1003, "msg": "密码错误"})
        with pytest.raises(AssertionError) as e:
            do_validate(resp, [{"eq": ["$.code", 0]}], case_name="密码错误")
        msg = str(e.value)
        assert "密码错误" in msg          # 用例名
        assert "$.code" in msg            # 表达式
        assert "1003" in msg and "0" in msg   # 实际值与期望值

    def test_空断言列表必须报错(self):
        """零断言 = 假绿的第一来源，必须拦死在入口"""
        with pytest.raises(ValueError) as e:
            do_validate(FakeResp(body={"code": 0}), [], case_name="零断言用例")
        assert "没有任何断言" in str(e.value)

    def test_未知算子必须报错(self):
        with pytest.raises(ValueError) as e:
            do_validate(FakeResp(body={"code": 0}), [{"equal": ["$.code", 0]}],
                        case_name="写错算子")
        assert "不支持的断言方式" in str(e.value)

    def test_路径未匹配必须报错(self):
        resp = FakeResp(body={"code": 0, "data": {}})
        with pytest.raises(AssertionError) as e:
            do_validate(resp, [{"is_null": ["$.data.non_exist_field"]}],
                        case_name="路径写错")
        assert "路径未匹配" in str(e.value)

    def test_ne配错路径不能恒真通过(self):
        """这是比零断言更隐蔽的一种假绿"""
        resp = FakeResp(body={"code": 0, "data": {"token": "t"}})
        with pytest.raises(AssertionError) as e:
            do_validate(resp, [{"ne": ["$.data.tokenn", "whatever"]}],
                        case_name="ne 路径写错")
        assert "路径未匹配" in str(e.value)

    @pytest.mark.parametrize("op", ["is_null", "not_null"])
    def test_null类算子多传参数要报错(self, op):
        """多传的参数不能被静默忽略——那说明写成了别的算子的格式"""
        resp = FakeResp(body={"code": 0})
        with pytest.raises(ValueError) as e:
            do_validate(resp, [{op: ["$.code", "多写的参数"]}], case_name="参数写多")
        assert "只接受 1 个参数" in str(e.value)

    def test_两参数算子少给参数要报错(self):
        resp = FakeResp(body={"code": 0})
        with pytest.raises(ValueError):
            do_validate(resp, [{"eq": ["$.code"]}], case_name="参数不足")

    def test_算子格式不对要报错(self):
        resp = FakeResp(body={"code": 0})
        with pytest.raises(ValueError):
            do_validate(resp, [{"eq": "$.code", "gt": "$.code"}], case_name="格式错")


# ================================================================ 用例结构校验

class TestValidateCase:

    OK_CASE = {
        "name": "合法用例",
        "request": {"method": "GET", "path": "/api/user/1"},
        "validate": [{"eq": ["$.code", 0]}],
    }

    def test_合法用例返回用例名(self):
        assert validate_case(self.OK_CASE) == "合法用例"

    def test_缺少validate字段必须报错(self):
        case = {"name": "漏写断言", "request": {"method": "GET", "path": "/x"}}
        with pytest.raises(ValueError) as e:
            validate_case(case)
        assert "缺少必填字段" in str(e.value)

    def test_validate拼成validates必须报错(self):
        """
        最危险的一种：一个字母的差别。
        以前这条用例哪怕请求参数故意写错、业务上必然失败，
        在报告里依然是一条绿色的 passed。
        """
        case = {"name": "字段名拼错",
                "request": {"method": "POST", "path": "/api/login",
                            "json": {"username": "admin", "password": "wrong"}},
                "validates": [{"eq": ["$.code", 1003]}]}
        with pytest.raises(ValueError) as e:
            validate_case(case)
        assert "未知字段" in str(e.value)

    def test_validate为空列表必须报错(self):
        case = dict(self.OK_CASE, validate=[])
        with pytest.raises(ValueError) as e:
            validate_case(case)
        assert "非空列表" in str(e.value)

    def test_request缺method或path必须报错(self):
        for bad_req in ({"path": "/x"}, {"method": "GET"}, {"method": "GET", "path": ""}):
            case = dict(self.OK_CASE, request=bad_req)
            with pytest.raises(ValueError):
                validate_case(case)

    def test_extract必须是字典(self):
        case = dict(self.OK_CASE, extract=["不是字典"])
        with pytest.raises(ValueError):
            validate_case(case)

    def test_非字典用例要报错(self):
        with pytest.raises(ValueError):
            validate_case(["这不是字典"])


# ================================================================ 用例文件加载

class TestLoadCases:

    def test_加载真实用例文件全部通过校验(self):
        for name in ("test_login.yaml", "test_order.yaml", "test_user.yaml"):
            path = os.path.join(_ROOT, "data", name)
            cases = load_cases(path)
            assert cases, f"{name} 里没有用例"
            # 每条用例都必须真的带断言
            for case in cases:
                assert case["validate"], f"{name} / {case.get('name')} 没有断言"

    def test_文件顶层不是列表要报错(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("name: 不是列表\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_cases(str(p))

    def test_文件里有拼错字段的用例要报错(self, tmp_path):
        p = tmp_path / "typo.yaml"
        p.write_text(
            "- name: 拼错了\n"
            "  request:\n"
            "    method: GET\n"
            "    path: /api/user/1\n"
            "  validates:\n"
            "    - eq: ['$.code', 0]\n",
            encoding="utf-8")
        with pytest.raises(ValueError) as e:
            load_cases(str(p))
        assert "未知字段" in str(e.value)


# ================================================================ 配置

class TestConfig:

    def test_默认环境是test(self):
        cfg = get_config()
        assert cfg.base_url == "http://127.0.0.1:5000"
        assert cfg.timeout == 10

    def test_可以按名字取环境(self):
        assert get_config("prod").base_url == "https://api.example.com"

    def test_环境名写错抛KeyError(self):
        with pytest.raises(KeyError):
            get_config("不存在的环境")

    def test_环境名错误信息里列出可选值(self):
        with pytest.raises(KeyError) as e:
            get_config("不存在的环境")
        assert "test" in str(e.value) and "prod" in str(e.value)
