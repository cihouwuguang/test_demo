# -*- coding: utf-8 -*-
"""
响应提取与接口依赖：JSONPath + 变量池

这是数据驱动框架的核心机制，Day 4 会把它做成框架的一部分。

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/03_extract_dependency.py
"""
import re

import requests
from jsonpath_ng import parse

BASE_URL = "http://127.0.0.1:5000"


def check_server():
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        print("错误：连不上 mock 服务，请先执行 python mock_server\\app.py")
        raise SystemExit(1)


# ---------------------------------------------------------------- 1. 笨办法

def demo_ugly():
    print("=" * 60)
    print("1. 笨办法：一层层取，深了就很难受")
    print("=" * 60)

    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/login",
                  json={"username": "admin", "password": "123456"})
    data = resp.json()

    token = data["data"]["token"]
    user_id = data["data"]["userId"]
    print(f"  token = data['data']['token'] = {token}")
    print(f"  user_id = data['data']['userId'] = {user_id}")

    print("\n  问题：")
    print("    - 层级深了写着烦（data['a']['b']['c'][0]['d']）")
    print("    - 字段不存在直接 KeyError，整个用例挂掉")
    print("    - 取列表里的元素还得先判断长度\n")


# ---------------------------------------------------------------- 2. JSONPath

def demo_jsonpath():
    print("=" * 60)
    print("2. JSONPath：用表达式取值")
    print("=" * 60)

    data = {
        "code": 0,
        "data": {
            "total": 2,
            "list": [
                {"id": 1, "username": "admin"},
                {"id": 2, "username": "tester"},
            ],
        },
    }

    exprs = [
        "$.code",
        "$.data.total",
        "$.data.list[0].username",
        "$.data.list[*].id",
        "$..username",
    ]

    for e in exprs:
        matches = parse(e).find(data)
        values = [m.value for m in matches]
        print(f"  {e:32} → {values}")

    print("\n  常用语法：")
    print("    $        根节点")
    print("    .name    取字段")
    print("    [0]      列表下标")
    print("    [*]      列表所有元素")
    print("    ..name   递归查找\n")


def extract(data, expr):
    """从响应里按 JSONPath 取值，取不到返回 None（不抛异常）"""
    matches = parse(expr).find(data)
    return matches[0].value if matches else None


# ---------------------------------------------------------------- 3. 变量池

VARS = {}


def replace_vars(data):
    """
    递归把字符串里的 ${xxx} 换成变量池里的真实值

    注意一个真实框架必踩的坑：
    如果整个字符串就是一个占位符，要保留原变量的类型，
    否则 ${user_id} 取出来的 int 5 会变成字符串 "5"，
    服务端按整数匹配用户 id 就失败了。
    """
    if isinstance(data, str):
        # 整串就是一个占位符 → 原样返回，保留类型
        full = re.fullmatch(r"\$\{(\w+)\}", data)
        if full:
            key = full.group(1)
            if key not in VARS:
                raise KeyError(
                    f"变量 ${{{key}}} 未在变量池中找到，当前变量：{list(VARS.keys())}")
            return VARS[key]

        # 部分替换（比如 "订单${order_id}号"）→ 只能转成字符串
        def _sub(m):
            key = m.group(1)
            if key not in VARS:
                raise KeyError(
                    f"变量 ${{{key}}} 未在变量池中找到，当前变量：{list(VARS.keys())}")
            return str(VARS[key])
        return re.sub(r"\$\{(\w+)\}", _sub, data)

    if isinstance(data, dict):
        return {k: replace_vars(v) for k, v in data.items()}
    if isinstance(data, list):
        return [replace_vars(i) for i in data]
    return data


def demo_var_pool():
    print("=" * 60)
    print("3. 变量池：${变量名} 占位符替换")
    print("=" * 60)

    s = requests.Session()

    # 第一步：登录，提取 token
    resp = s.post(f"{BASE_URL}/api/login",
                  json={"username": "admin", "password": "123456"})
    VARS["token"] = extract(resp.json(), "$.data.token")
    VARS["user_id"] = extract(resp.json(), "$.data.userId")
    print(f"  提取到变量：{VARS}")

    s.headers.update({"token": VARS["token"]})

    # 第二步：创建用户，提取新用户的 id
    resp = s.post(f"{BASE_URL}/api/user",
                  json={"username": "var_test", "phone": "13700000000"})
    VARS["new_user_id"] = extract(resp.json(), "$.data.id")
    print(f"  新增用户后变量池：{VARS}")

    # 第三步：用例里只写占位符
    case_body = {"userId": "${new_user_id}", "amount": 88.8}
    print(f"\n  用例里写的：      {case_body}")
    real_body = replace_vars(case_body)
    print(f"  替换后实际发送的：{real_body}")
    print(f"  userId 的类型：{type(real_body['userId']).__name__}"
          f"    ← 是 int，不是字符串")

    # 第四步：用替换后的参数发请求
    resp = s.post(f"{BASE_URL}/api/order", json=real_body)
    print(f"  下单响应：{resp.json()}")

    print("\n  这就是接口依赖的通用解法：提取 → 存池 → 占位 → 替换\n")


def demo_type_pitfall():
    print("=" * 60)
    print("3.5 坑：占位符替换后类型变了")
    print("=" * 60)

    VARS.clear()
    VARS["user_id"] = 5          # int

    print("  如果替换时一律 str() 强转：")
    print("    {'userId': '${user_id}'} → {'userId': '5'}   类型是 str")
    print("    服务端按整数查用户 → 查不到 → 报'用户不存在'")
    print("    这种 bug 特别难查，因为肉眼看参数明明是对的")

    print("\n  正确做法：整串就是一个占位符时，保留原类型")
    result = replace_vars({"userId": "${user_id}"})
    print(f"    现在的结果：{result}，类型 {type(result['userId']).__name__}")

    print("\n  部分替换（占位符只是一部分）时仍要转字符串：")
    result2 = replace_vars({"desc": "订单${user_id}号"})
    print(f"    {result2}")

    print("\n  结论：写替换函数时一定要区分'整串占位符'和'部分占位符'\n")


# ---------------------------------------------------------------- 4. 完整链路

def demo_full_chain():
    print("=" * 60)
    print("4. 实战：登录 → 建用户 → 下单 → 查订单（完整依赖链）")
    print("=" * 60)

    s = requests.Session()
    VARS.clear()

    # 1 登录
    r = s.post(f"{BASE_URL}/api/login",
               json={"username": "admin", "password": "123456"})
    VARS["token"] = extract(r.json(), "$.data.token")
    s.headers.update({"token": VARS["token"]})
    print(f"  ① 登录 → token={VARS['token'][:16]}...")

    # 2 建用户
    r = s.post(f"{BASE_URL}/api/user",
               json={"username": "chain_user", "phone": "13611112222"})
    VARS["user_id"] = extract(r.json(), "$.data.id")
    print(f"  ② 建用户 → id={VARS['user_id']}")

    # 3 下单（用占位符）
    body = replace_vars({"userId": "${user_id}", "amount": 199.9,
                         "goodsName": "测试商品"})
    r = s.post(f"{BASE_URL}/api/order", json=body)
    VARS["order_id"] = extract(r.json(), "$.data.orderId")
    print(f"  ③ 下单 → orderId={VARS['order_id']}")
    if VARS["order_id"] is None:
        print(f"     下单失败，接口返回：{r.json()}，后续步骤跳过")
        return

    # 4 查订单
    r = s.get(f"{BASE_URL}/api/order/{VARS['order_id']}")
    print(f"  ④ 查订单 → {r.json()['data']}")

    # 5 支付
    r = s.post(f"{BASE_URL}/api/order/{VARS['order_id']}/pay")
    print(f"  ⑤ 支付 → 状态={r.json()['data']['status']}")

    print("\n  一条链路上每个接口都依赖前一个的返回值")
    print("  没有变量池的话，这些 id 只能手动复制，没法自动化\n")


# ---------------------------------------------------------------- 5. 脏数据问题

def demo_dirty_data():
    print("=" * 60)
    print("5. 坑：用例失败时，变量池可能是脏的")
    print("=" * 60)

    s = requests.Session()
    s.headers.update({"token": "mock_token_abc123"})

    print("  查一个不存在的用户：")
    r = s.get(f"{BASE_URL}/api/user/99999")
    print(f"    响应：{r.json()}")

    uid = extract(r.json(), "$.data.id")
    print(f"    提取 $.data.id → {uid}")
    if uid is None:
        print("    extract 返回 None，不会抛异常 —— 这就是为什么要用 extract 而不是直接取")

    print("\n  结论：")
    print("    - 提取函数取不到要返回 None，不能直接 KeyError 崩掉")
    print("    - 变量池里没有的变量，替换时要明确报错，方便定位")
    print("    - 上游失败时下游用例应该标记'跳过'而不是'失败'（Day 3 讲 skip）\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    demo_ugly()
    demo_jsonpath()
    demo_var_pool()
    demo_type_pitfall()
    demo_full_chain()
    demo_dirty_data()

    print("=" * 60)
    print("完成。记住：提取 → 存池 → 占位 → 替换")
    print("=" * 60)
