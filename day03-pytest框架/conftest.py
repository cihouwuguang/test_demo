# -*- coding: utf-8 -*-
"""
conftest.py —— pytest 的特殊文件

放在这里定义的 fixture，对同级及所有子目录的用例自动可见，
用例里不用 import 就能直接用。

运行方式：
    cd day03-pytest框架
    pytest -vs
"""
import time

import pytest
import requests

BASE_URL = "http://127.0.0.1:5000"


# ---------------------------------------------------------------- 环境检查

@pytest.fixture(scope="session", autouse=True)
def check_mock_server():
    """
    会话级 + autouse：所有用例开始前自动执行一次
    连不上 mock 服务就直接退出，给出清晰提示，而不是让几十条用例全红
    """
    try:
        requests.get(BASE_URL, timeout=3)
    except requests.exceptions.RequestException:
        pytest.exit(
            "\n" + "=" * 60 +
            "\n连不上 mock 服务！\n请先另开一个终端执行：\n"
            "    python mock_server\\app.py\n" + "=" * 60,
            returncode=1,
        )


# ---------------------------------------------------------------- 登录 fixture

@pytest.fixture(scope="session")
def token():
    """
    session 级：整个测试过程只登录一次

    注意这里用的是 yield 而不是 return ——
    yield 之后的代码在所有用例跑完后执行（Day 1 的知识点）
    """
    print("\n[session 前置] 调用登录接口")
    resp = requests.post(f"{BASE_URL}/api/login",
                         json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200, "登录接口 HTTP 状态码异常"
    t = resp.json()["data"]["token"]
    print(f"[session 前置] 拿到 token：{t}")

    yield t      # ← 分界线

    print("\n[session 后置] 所有用例跑完，退出登录")


@pytest.fixture(scope="session")
def api(token):
    """
    依赖 token fixture，返回一个已登录的 Session
    这演示了 fixture 之间可以互相依赖
    """
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "token": token})
    print("[session 前置] 创建已登录的 Session")

    yield s

    print("[session 后置] 关闭 Session")
    s.close()


# ---------------------------------------------------------------- 数据准备 fixture

@pytest.fixture
def temp_user(api):
    """
    function 级（默认）：每条用例执行前创建一个用户，执行后删掉

    这就是 yield 做前后置最典型的用法：
    - yield 之前：造数据
    - yield 之后：清数据
    即使用例失败，清理代码也会执行
    """
    username = f"tmp_{int(time.time() * 1000) % 100000}"
    print(f"\n  [用例前置] 创建临时用户 {username}")
    r = api.post(f"{BASE_URL}/api/user",
                 json={"username": username, "phone": "13700000000"})
    assert r.json()["code"] == 0, f"创建测试用户失败：{r.text}"
    user_id = r.json()["data"]["id"]

    yield {"id": user_id, "username": username}

    print(f"  [用例后置] 删除临时用户 {username}")
    api.delete(f"{BASE_URL}/api/user/{user_id}")


# ---------------------------------------------------------------- 自动计时

@pytest.fixture(autouse=True)
def case_timer():
    """每条用例自动计时（autouse：不用声明也会生效）"""
    start = time.time()
    yield
    cost = time.time() - start
    print(f"  [耗时] {cost:.3f} 秒")
