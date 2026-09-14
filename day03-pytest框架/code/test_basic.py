# -*- coding: utf-8 -*-
"""
pytest 基础：命名规则、断言、失败信息

运行：pytest day03-pytest框架/code/test_basic.py -vs
"""
import pytest


# ---------------------------------------------------------------- 1. 最简用例

def test_add():
    assert 1 + 1 == 2


def test_string():
    assert "hello".upper() == "HELLO"


# ---------------------------------------------------------------- 2. 断言带提示信息

@pytest.mark.xfail(reason="故意写错，用来演示失败信息长什么样")
def test_with_msg():
    """推荐写法：每个断言都加 message，排查效率翻倍"""
    result = 10
    expected = 20
    assert result == expected, f"期望 {expected}，实际 {result}"


# ---------------------------------------------------------------- 3. 各种断言

def test_assert_types():
    assert 1 == 1                      # 相等
    assert 1 != 2                      # 不等
    assert 3 > 2                       # 大小
    assert "a" in ["a", "b"]           # 包含
    assert "token" in "my_token_123"   # 子串
    assert {"a": 1}.get("a") == 1      # 字典取值


# ---------------------------------------------------------------- 4. 断言异常

def test_raises():
    """测试'参数非法时应该抛异常'这类场景"""
    with pytest.raises(ValueError):
        int("abc")


def test_raises_with_match():
    """还能校验异常信息的内容"""
    with pytest.raises(ValueError, match="invalid literal"):
        int("abc")


# ---------------------------------------------------------------- 5. 浮点断言

def test_float():
    """金额比较绝不能用 ==，要用差值或 approx"""
    a = 0.1 + 0.2
    assert a != 0.3                       # 这就是浮点数的坑
    assert abs(a - 0.3) < 0.01            # 解法一：比较差值
    assert a == pytest.approx(0.3)        # 解法二：pytest 的近似比较


# ---------------------------------------------------------------- 6. 类形式的用例

class TestUser:
    """类名必须 Test 开头，且不能有 __init__ 方法"""

    def test_in_class(self):
        assert True

    def test_another(self):
        assert "pytest" in "pytest 好用"


# ---------------------------------------------------------------- 7. 故意失败（看失败信息长啥样）

@pytest.mark.xfail(reason="故意写错，用来演示失败信息长什么样")
def test_fail_demo():
    """故意写个失败的，看看 pytest 的失败信息有多详细"""
    left = {"name": "admin", "role": "admin"}
    right = {"name": "admin", "role": "user"}
    assert left == right, "两个用户对象不一致"
