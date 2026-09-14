# -*- coding: utf-8 -*-
"""
实战：把 Day 2 的脚本改造成 pytest 用例

可以对比一下改造前后的差别：
  改造前：手动 print 结果，失败也不会中断，多条用例靠复制粘贴
  改造后：有断言、有报告、有前后置清理、数据参数化

运行：pytest day03-pytest框架/code/test_api.py -vs
"""
import pytest

from conftest import BASE_URL


# ---------------------------------------------------------------- 1. 登录

@pytest.mark.smoke
def test_login_success(api):
    """登录成功"""
    r = api.post(f"{BASE_URL}/api/login",
                 json={"username": "admin", "password": "123456"})

    # 两层断言：HTTP 状态码 + 业务 code
    assert r.status_code == 200, f"HTTP 状态码异常：{r.status_code}"
    body = r.json()
    assert body["code"] == 0, f"业务 code 不为 0，响应：{r.text}"
    assert "token" in body["data"], f"响应里没有 token：{r.text}"


@pytest.mark.parametrize("username, password, expect_code", [
    ("admin", "wrong", 1003),
    ("", "123456", 1001),
    ("a", "123456", 1002),
])
def test_login_fail(api, username, password, expect_code):
    """登录失败的几种情况"""
    r = api.post(f"{BASE_URL}/api/login",
                 json={"username": username, "password": password})
    assert r.status_code == 200, f"HTTP 状态码异常：{r.status_code}"
    assert r.json()["code"] == expect_code, \
        f"期望 code={expect_code}，实际响应：{r.text}"


# ---------------------------------------------------------------- 2. 用户查询

def test_get_user(api):
    r = api.get(f"{BASE_URL}/api/user/1")
    assert r.json()["code"] == 0
    data = r.json()["data"]
    assert data["id"] == 1
    assert "username" in data


def test_get_user_not_exist(api):
    r = api.get(f"{BASE_URL}/api/user/99999")
    assert r.json()["code"] == 2001, f"期望'用户不存在'，实际：{r.text}"


def test_no_token():
    """不带 token 应该被拒绝 —— 这是安全用例，别漏"""
    import requests
    r = requests.get(f"{BASE_URL}/api/user/1")       # 故意不用 api（它带 token）
    assert r.status_code == 401, f"期望 401，实际 {r.status_code}"


# ---------------------------------------------------------------- 3. 使用 temp_user fixture

def test_temp_user_created(api, temp_user):
    """
    temp_user 是 conftest.py 里定义的 fixture：
      - 用例执行前创建一个临时用户
      - 用例执行后自动删掉（就算用例失败也会删）
    """
    print(f"\n  用例拿到的临时用户：{temp_user}")
    r = api.get(f"{BASE_URL}/api/user/{temp_user['id']}")
    assert r.json()["code"] == 0, f"查不到刚创建的用户：{r.text}"
    assert r.json()["data"]["username"] == temp_user["username"]


def test_temp_user_isolated(api, temp_user):
    """每条用例拿到的都是新用户，互不影响"""
    print(f"\n  这条用例的临时用户：{temp_user}")
    r = api.get(f"{BASE_URL}/api/user/{temp_user['id']}")
    assert r.json()["code"] == 0


# ---------------------------------------------------------------- 4. 完整业务链路

def test_order_flow(api, temp_user):
    """
    完整链路：建用户 → 下单 → 查订单 → 支付

    注意：这里用的是 temp_user 建的临时用户，
    测完 fixture 会自动删掉，不会留脏数据
    """
    # 1 下单
    r = api.post(f"{BASE_URL}/api/order", json={
        "userId": temp_user["id"],
        "amount": 99.9,
        "goodsName": "自动化下单测试",
    })
    assert r.json()["code"] == 0, f"下单失败：{r.text}"
    order_id = r.json()["data"]["orderId"]
    print(f"\n  下单成功，orderId={order_id}")

    # 2 查订单
    r = api.get(f"{BASE_URL}/api/order/{order_id}")
    assert r.json()["code"] == 0
    assert r.json()["data"]["status"] == "CREATED"
    assert abs(r.json()["data"]["amount"] - 99.9) < 0.01

    # 3 支付
    r = api.post(f"{BASE_URL}/api/order/{order_id}/pay")
    assert r.json()["code"] == 0, f"支付失败：{r.text}"
    assert r.json()["data"]["status"] == "PAID"

    # 4 重复支付应该被拒绝（幂等性）
    r = api.post(f"{BASE_URL}/api/order/{order_id}/pay")
    assert r.json()["code"] == 3004, \
        f"重复支付应该被拒绝，实际返回：{r.text}"


# ---------------------------------------------------------------- 5. 异常场景

def test_timeout(api):
    """超时的处理"""
    import requests
    with pytest.raises(requests.exceptions.Timeout):
        api.get(f"{BASE_URL}/api/slow", timeout=1)


def test_server_error(api):
    """服务端报错时，客户端不能崩"""
    r = api.get(f"{BASE_URL}/api/error")
    assert r.status_code == 500, f"期望 500，实际 {r.status_code}"
    print(f"\n  服务端返回 500，客户端正常处理，没有崩溃")
