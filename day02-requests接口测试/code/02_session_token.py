# -*- coding: utf-8 -*-
"""
Session 与鉴权：登录一次，全局复用

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/02_session_token.py
"""
import requests

BASE_URL = "http://127.0.0.1:5000"


def check_server():
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        print("错误：连不上 mock 服务，请先执行 python mock_server\\app.py")
        raise SystemExit(1)


# ---------------------------------------------------------------- 1. 不用 Session 的麻烦

def demo_without_session():
    print("=" * 60)
    print("1. 不用 Session：每次都要手动带 token")
    print("=" * 60)

    # 登录
    resp = requests.post(f"{BASE_URL}/api/login",
                         json={"username": "admin", "password": "123456"})
    token = resp.json()["data"]["token"]
    print(f"  登录拿到 token：{token}")

    # 每个请求都要手动加 headers
    for path in ["/api/user/1", "/api/users?page=1&size=2"]:
        requests.get(BASE_URL + path, headers={"token": token})
        print(f"  请求 {path}：手动加了 header")

    print("  麻烦：3 个接口写 3 遍，漏一个就 401\n")


# ---------------------------------------------------------------- 2. 用 Session

def demo_with_session():
    print("=" * 60)
    print("2. 用 Session：设置一次，全局生效")
    print("=" * 60)

    s = requests.Session()

    # 统一设置默认请求头
    s.headers.update({"Content-Type": "application/json"})
    print("  设置了默认 Content-Type，后续请求自动带上")

    # 登录
    resp = s.post(f"{BASE_URL}/api/login",
                  json={"username": "admin", "password": "123456"})
    token = resp.json()["data"]["token"]

    # 把 token 放进 Session 的默认头
    s.headers.update({"token": token})
    print(f"  把 token 放进 Session 默认头：{token}")

    # 后续请求不用再管鉴权
    for path in ["/api/user/1", "/api/users?page=1&size=2"]:
        r = s.get(BASE_URL + path)
        print(f"  请求 {path} → {r.status_code}，响应 code={r.json()['code']}")

    print("\n  不用 Session 的话这里每个都要手写 headers={'token': token}\n")


# ---------------------------------------------------------------- 3. Session 自动管 cookie

def demo_cookie():
    print("=" * 60)
    print("3. Session 会自动保存和携带 cookie")
    print("=" * 60)

    s = requests.Session()
    print(f"  初始 cookies：{dict(s.cookies)}")

    # 手动往 cookie jar 里放一个，看看它会不会自动带出去
    s.cookies.set("sessionid", "abc123")
    print(f"  放入 cookie 后：{dict(s.cookies)}")

    resp = s.get(f"{BASE_URL}/api/user/1",
                 headers={"token": "mock_token_abc123"})
    sent = resp.request.headers.get("Cookie")
    print(f"  这次请求实际发出的 Cookie 头：{sent}")
    print("  看，我们没手动写 Cookie，Session 自动带上了")

    print("\n  完整流程：服务端响应 Set-Cookie → Session 存进 cookie jar")
    print("            → 后续请求自动带上 → 不用手动传凭证\n")


# ---------------------------------------------------------------- 4. 连接复用

def demo_keep_alive():
    print("=" * 60)
    print("4. Session 复用 TCP 连接，性能更好")
    print("=" * 60)

    import time

    # 不用 Session：每次新建连接
    start = time.time()
    for _ in range(5):
        requests.get(f"{BASE_URL}/api/users",
                     headers={"token": "mock_token_abc123"})
    cost_no_session = time.time() - start

    # 用 Session：复用连接池
    s = requests.Session()
    s.headers.update({"token": "mock_token_abc123"})
    start = time.time()
    for _ in range(5):
        s.get(f"{BASE_URL}/api/users")
    cost_session = time.time() - start

    print(f"  不用 Session，5 次请求：{cost_no_session:.4f} 秒")
    print(f"  用 Session，  5 次请求：{cost_session:.4f} 秒")
    print("  用例多的时候差距会放大\n")


# ---------------------------------------------------------------- 5. 鉴权失败的处理

def demo_auth_fail():
    print("=" * 60)
    print("5. 401 和 403 的区别，以及自动化里怎么处理")
    print("=" * 60)

    # 401：没带 token
    r1 = requests.get(f"{BASE_URL}/api/user/1")
    print(f"  不带 token：    HTTP {r1.status_code}，{r1.json()['msg']}")

    # 401：token 错误
    r2 = requests.get(f"{BASE_URL}/api/user/1", headers={"token": "wrong_token"})
    print(f"  token 错误：    HTTP {r2.status_code}，{r2.json()['msg']}")

    # 正常
    r3 = requests.get(f"{BASE_URL}/api/user/1", headers={"token": "mock_token_abc123"})
    print(f"  token 正确：    HTTP {r3.status_code}，{r3.json()['msg']}")

    print("\n  401 = 你谁啊（没认证）")
    print("  403 = 我知道你是谁，但你没权限（认证了但授权不够）")
    print("  自动化里遇到 401 通常是前置登录没做好，不是 bug\n")


# ---------------------------------------------------------------- 6. token 过期自动重登

class ApiClient:
    """演示：token 失效时自动重新登录"""

    def __init__(self, base_url):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._token = None

    def login(self):
        resp = self.session.post(f"{self.base_url}/api/login",
                                 json={"username": "admin", "password": "123456"})
        self._token = resp.json()["data"]["token"]
        self.session.headers.update({"token": self._token})
        print(f"    已登录，token={self._token}")
        return self._token

    def get(self, path):
        """带自动重登的 get"""
        resp = self.session.get(self.base_url + path)
        if resp.status_code == 401:
            print("    检测到 401，token 过期，自动重新登录")
            self.login()
            resp = self.session.get(self.base_url + path)
        return resp


def demo_auto_relogin():
    print("=" * 60)
    print("6. 实战：token 过期自动重登")
    print("=" * 60)

    client = ApiClient(BASE_URL)
    client.login()

    print("  正常请求：")
    r = client.get("/api/user/1")
    print(f"    → {r.status_code}")

    print("\n  手动把 token 改坏，模拟过期：")
    client.session.headers.update({"token": "expired"})
    r = client.get("/api/user/1")
    print(f"    → {r.status_code}（自动重登后成功）\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    demo_without_session()
    demo_with_session()
    demo_cookie()
    demo_keep_alive()
    demo_auth_fail()
    demo_auto_relogin()

    print("=" * 60)
    print("完成。记住：登录一次，把 token 放进 Session 默认头")
    print("=" * 60)
