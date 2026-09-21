# -*- coding: utf-8 -*-
"""
requests 基础：GET/POST、三个传参参数的区别、响应处理

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/01_requests_basic.py
"""
import requests

BASE_URL = "http://127.0.0.1:5000"


def check_server():
    """确认 mock 服务在跑"""
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        print("=" * 60)
        print("错误：连不上 mock 服务")
        print("请另开一个终端，执行：python mock_server\\app.py")
        print("=" * 60)
        raise SystemExit(1)


# ---------------------------------------------------------------- 1. 最简单的 GET

def demo_get():
    print("=" * 60)
    print("1. 最简单的 GET 请求")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/api/users", headers={"token": "mock_token_abc123"})
    print(f"  status_code：{resp.status_code}")
    print(f"  headers['Content-Type']：{resp.headers.get('Content-Type')}")
    print(f"  elapsed（耗时）：{resp.elapsed.total_seconds():.4f} 秒")
    print(f"  text（字符串）：{resp.text[:80]}...")
    print(f"  json()（字典）：{resp.json()}")
    print()


# ---------------------------------------------------------------- 2. params

def demo_params():
    print("=" * 60)
    print("2. params —— 拼到 URL 后面（GET 常用）")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/api/users",
                        params={"page": 1, "size": 1},
                        headers={"token": "mock_token_abc123"})
    print(f"  实际请求的 URL：{resp.url}")
    print("  看，参数自动拼成了 ?page=1&size=1")
    print(f"  响应：{resp.json()}\n")


# ---------------------------------------------------------------- 3. data vs json（重点）

def demo_data_vs_json():
    print("=" * 60)
    print("3. data 和 json 的区别（最容易踩的坑）")
    print("=" * 60)

    print("  【正确】用 json= 传 JSON：")
    resp = requests.post(f"{BASE_URL}/api/login",
                         json={"username": "admin", "password": "123456"})
    print(f"    请求头 Content-Type：{resp.request.headers.get('Content-Type')}")
    print(f"    请求体：{resp.request.body}")
    print(f"    响应：{resp.json()}\n")

    print("  【错误】接口要求 JSON，却用了 data=：")
    resp2 = requests.post(f"{BASE_URL}/api/login",
                          data={"username": "admin", "password": "123456"})
    print(f"    请求头 Content-Type：{resp2.request.headers.get('Content-Type')}")
    print(f"    请求体：{resp2.request.body}")
    print(f"    响应：{resp2.json()}    ← 服务端解析不到参数")
    print("\n  结论：看接口文档的 Content-Type 要求，现在大多数用 json=\n")


# ---------------------------------------------------------------- 4. 常见状态码

def demo_status_code():
    print("=" * 60)
    print("4. 常见状态码与处理")
    print("=" * 60)

    cases = [
        ("正常请求", f"{BASE_URL}/api/users", {"token": "mock_token_abc123"}),
        ("没有 token（401）", f"{BASE_URL}/api/users", {}),
        ("路径不存在（404）", f"{BASE_URL}/api/not-exist", {}),
        ("服务端报错（500）", f"{BASE_URL}/api/error", {}),
    ]

    for name, url, headers in cases:
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            print(f"  {name}：HTTP {resp.status_code}")
            print(f"      业务响应：{resp.text[:100]}")
        except requests.exceptions.RequestException as e:
            print(f"  {name}：请求异常 {type(e).__name__}")

    print("\n  注意：requests 不会因为 404/500 自动抛异常！")
    print("        它认为'拿到响应'就算成功，要手动判断或用 raise_for_status()\n")


# ---------------------------------------------------------------- 5. raise_for_status

def demo_raise_for_status():
    print("=" * 60)
    print("5. raise_for_status：让错误状态码变成异常")
    print("=" * 60)

    resp = requests.get(f"{BASE_URL}/api/not-exist")
    print(f"  不调用时：status_code={resp.status_code}，程序正常往下走")

    try:
        resp.raise_for_status()
        print("  不会打印这行")
    except requests.exceptions.HTTPError as e:
        print(f"  调用后抛异常：{e}\n")


# ---------------------------------------------------------------- 6. raise_for_status 的坑

def demo_raise_pitfall():
    print("=" * 60)
    print("6. 坑：HTTP 200 但业务失败")
    print("=" * 60)

    resp = requests.post(f"{BASE_URL}/api/login",
                         json={"username": "admin", "password": "wrong"})
    print(f"  HTTP 状态码：{resp.status_code}    ← 是 200！")
    print(f"  响应体：{resp.json()}    ← 业务 code=1003 表示失败")
    print("\n  结论：断言要两层都做 —— HTTP 状态码 + 业务 code")
    print("        只判断 status_code == 200 会漏掉大量业务 bug\n")


# ---------------------------------------------------------------- 7. timeout

def demo_timeout():
    print("=" * 60)
    print("7. timeout：不加会一直挂着")
    print("=" * 60)

    print("  调 /api/slow（要 3 秒），只给 1 秒超时：")
    try:
        requests.get(f"{BASE_URL}/api/slow", timeout=1)
        print("    居然成功了？")
    except requests.exceptions.Timeout:
        print("    捕获 Timeout 异常（符合预期）")

    print("\n  给 5 秒超时：")
    resp = requests.get(f"{BASE_URL}/api/slow", timeout=5)
    print(f"    成功：{resp.json()}")
    print("\n  结论：框架里必须设默认超时，否则一个接口卡死会拖垮整个测试")
    print("  [!] 但别把 timeout 理解成「请求总共最多等 N 秒」——")
    print("     它是 connect 和 read 两个独立超时，read 指的是"
          "「两次收到字节之间的间隔」。")
    print("     code/05_sign_and_exception.py 第 4 节用「慢速滴流服务」证明了这一点，")
    print("     建议跑一遍再下结论。\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    demo_get()
    demo_params()
    demo_data_vs_json()
    demo_status_code()
    demo_raise_for_status()
    demo_raise_pitfall()
    demo_timeout()

    print("=" * 60)
    print("完成。记住：GET 用 params，POST 看 Content-Type 选 data 还是 json")
    print("=" * 60)
