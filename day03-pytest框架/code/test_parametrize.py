# -*- coding: utf-8 -*-
"""
参数化：一份逻辑，多组数据

这是"数据驱动"的雏形。Day 4 会把数据挪到 YAML 文件里。

运行：pytest day03-pytest框架/code/test_parametrize.py -vs
"""
import pytest

from conftest import BASE_URL


# ---------------------------------------------------------------- 1. 基本参数化

@pytest.mark.parametrize("username, password, expect_code", [
    ("admin", "123456", 0),          # 正确
    ("admin", "wrong", 1003),        # 密码错误
    ("", "123456", 1001),            # 用户名为空
    ("a", "123456", 1002),           # 用户名太短
    ("a" * 21, "123456", 1002),      # 用户名太长
])
def test_login_params(api, username, password, expect_code):
    """5 组数据，只写了一份逻辑"""
    r = api.post(f"{BASE_URL}/api/login",
                 json={"username": username, "password": password})
    assert r.status_code == 200, f"HTTP 状态码异常：{r.status_code}"
    assert r.json()["code"] == expect_code, \
        f"期望业务 code={expect_code}，实际响应：{r.text}"


# ---------------------------------------------------------------- 2. 参数是字典

@pytest.mark.parametrize("case", [
    {"name": "正常查询", "uid": 1, "expect_code": 0},
    {"name": "查不存在的用户", "uid": 99999, "expect_code": 2001},
])
def test_with_dict(api, case):
    """参数是字典时，用例可读性更好（能带用例名）"""
    r = api.get(f"{BASE_URL}/api/user/{case['uid']}")
    assert r.json()["code"] == case["expect_code"], \
        f"用例【{case['name']}】失败，响应：{r.text}"


# ---------------------------------------------------------------- 3. 多重参数化（笛卡尔积）

@pytest.mark.parametrize("page", [1, 2])
@pytest.mark.parametrize("size", [1, 5])
def test_pagination(api, page, size):
    """两个装饰器叠加 → 2 × 2 = 4 条用例"""
    r = api.get(f"{BASE_URL}/api/users", params={"page": page, "size": size})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["page"] == page
    assert data["size"] == size
    assert len(data["list"]) <= size


# ---------------------------------------------------------------- 4. 给用例起个好名字

@pytest.mark.parametrize("username, password, expect_code", [
    pytest.param("admin", "123456", 0, id="登录成功"),
    pytest.param("admin", "wrong", 1003, id="密码错误"),
    pytest.param("", "123456", 1001, id="用户名为空"),
])
def test_with_ids(api, username, password, expect_code):
    """用 pytest.param(id=...) 让报告里的用例名看得懂"""
    r = api.post(f"{BASE_URL}/api/login",
                 json={"username": username, "password": password})
    assert r.json()["code"] == expect_code


# ---------------------------------------------------------------- 5. 期望抛异常的参数化

@pytest.mark.parametrize("value, should_raise", [
    ("123", False),
    ("abc", True),
    ("", True),
])
def test_int_convert(value, should_raise):
    """同一份逻辑，既能测正常也能测异常"""
    if should_raise:
        with pytest.raises(ValueError):
            int(value)
    else:
        assert int(value) == 123
