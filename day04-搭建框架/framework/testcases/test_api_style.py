# -*- coding: utf-8 -*-
"""
代码式用例 —— 演示框架支持的第二种写法

什么时候用 YAML，什么时候写代码？

  YAML 数据驱动：
    适合"请求-断言"的简单场景，加用例不用写代码，业务同事也能维护

  代码式（本文件）：
    适合有逻辑的场景 —— 循环、条件判断、多接口组合、需要特殊处理

成熟的框架两种都支持，不是非此即彼。
面试时能说出"什么时候用哪种"，比只会一种强。
"""
import pytest

from api.order_api import OrderAPI
from api.user_api import UserAPI


def test_login_with_api_class(client):
    """用业务类调用，代码更简洁"""
    user_api = UserAPI(client)
    r = user_api.login("admin", "123456")

    assert r.status_code == 200
    assert r.json()["code"] == 0
    assert r.json()["data"]["username"] == "admin"


def test_loop_check(client):
    """需要循环的场景，YAML 表达不了，写代码更合适"""
    user_api = UserAPI(client)

    for uid in [1, 2]:
        r = user_api.get_user(uid)
        assert r.json()["code"] == 0, f"用户 {uid} 查询失败：{r.text}"
        assert "username" in r.json()["data"]


def test_conditional_logic(client):
    """需要条件判断的场景"""
    user_api = UserAPI(client)
    r = user_api.get_user(99999)

    if r.json()["code"] == 2001:
        # 用户不存在，走另一条分支
        r2 = user_api.create_user("cond_user", "13500009999")
        assert r2.json()["code"] == 0
        user_api.delete_user(r2.json()["data"]["id"])
    else:
        pytest.fail(f"期望返回'用户不存在'，实际：{r.text}")


@pytest.mark.smoke
def test_full_business_flow(client):
    """
    完整业务链路：建用户 → 下单 → 支付 → 校验状态

    这种跨模块的组合场景，写代码比写 YAML 清楚
    """
    user_api = UserAPI(client)
    order_api = OrderAPI(client)

    # 1 建用户
    r = user_api.create_user("flow_user", "13400001111")
    assert r.json()["code"] == 0, f"创建用户失败：{r.text}"
    user_id = r.json()["data"]["id"]

    try:
        # 2 下单
        r = order_api.create_order(user_id, 88.8, "流程测试商品")
        assert r.json()["code"] == 0, f"下单失败：{r.text}"
        order_id = r.json()["data"]["orderId"]
        assert r.json()["data"]["status"] == "CREATED"

        # 3 支付
        r = order_api.pay_order(order_id)
        assert r.json()["code"] == 0, f"支付失败：{r.text}"
        assert r.json()["data"]["status"] == "PAID"

        # 4 查订单确认状态
        r = order_api.get_order(order_id)
        assert r.json()["data"]["status"] == "PAID"

    finally:
        # 无论成功失败都清理，避免脏数据
        user_api.delete_user(user_id)
