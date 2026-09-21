# -*- coding: utf-8 -*-
"""
签名接口与异常场景处理

签名在金融/支付类接口里几乎是标配。你在华为钱包做过的报文签名属于同一类东西。

[!] 术语先对齐（说错会被金融/终端方向的面试官当场标记）：
    签名 = JWS（RFC 7515）   —— 防篡改，payload 是 base64url，**可读**
    加密 = JWE（RFC 7516）   —— 防窃听，内容不可读
    JWT  = token 的格式（RFC 7519），默认是 JWS：只签名不加密
    「RSA 私钥签名 + 对方公钥/服务端验签」描述的是 JWS(RS256)，不是 JWE。
    （你当时参与的那个项目具体用的是哪个标准，以你自己确认为准，不要照抄这段。）

本文件的一个原则：**该断言的地方就写 assert**。
    签名算错了、服务端没拒绝篡改，脚本必须直接失败，
    而不是 print 一句"响应是 xxx"让你用眼睛判断。
    这正是"测试脚本"和"演示脚本"的区别。

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/05_sign_and_exception.py
"""
import hashlib
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

BASE_URL = "http://127.0.0.1:5000"

# 本机地址必须绕过系统代理
#
# 为什么脚本里要写这两行？
#   机器上开着代理软件（Clash 之类）时，requests 会读环境变量 HTTP_PROXY，
#   连 127.0.0.1:5000 这种本机地址也照样发去代理。代理进程一不在，
#   本脚本所有请求立刻失败，而报错看起来像是"服务没启动"——排查方向完全错了。
#   真实项目推荐在系统环境变量里设 NO_PROXY=127.0.0.1,localhost；
#   写在这里是为了脚本在任何人的机器上都能一次跑通（且只影响本进程）。
import os
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
SIGN_KEY = "demo_secret_key"


def check_server():
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        print("错误：连不上 mock 服务，请先执行 python mock_server\\app.py")
        raise SystemExit(1)


# ---------------------------------------------------------------- 1. 签名是什么

def demo_what_is_sign():
    print("=" * 60)
    print("1. 签名到底在防什么")
    print("=" * 60)

    print("  没有签名时，请求被中间人截获后可以随便改：")
    print("    {'amount': 1}  →  改成  {'amount': 100000}")
    print("    服务端无从判断参数有没有被篡改")
    print()
    print("  加了签名之后：")
    print("    sign = md5(密钥 + 参数 + 时间戳)")
    print("    改了参数 → 签名对不上 → 服务端拒绝")
    print()
    print("  签名解决三个问题：")
    print("    ① 防篡改：参数改了签名就对不上")
    print("    ② 防重放：带时间戳，过期请求作废；带 nonce 防止重复提交")
    print("    ③ 验身份：密钥只有双方知道，能确认是谁发的")
    print()
    print("  注意：签名 ≠ 加密。")
    print("    签名（JWS）防篡改，内容还是明文可读；")
    print("    加密（JWE）防窃听，内容不可读。")
    print("    要又防篡改又防窃听，就得先加密再签名（两个标准一起用）。")
    print("    现实中敏感数据（身份证、银行卡）还要叠加 HTTPS + 字段级加密。\n")


# ---------------------------------------------------------------- 2. 实现签名

def calc_sign(body: dict, timestamp: str, key: str = SIGN_KEY) -> str:
    """
    签名规则：md5(密钥 + 参数按 key 升序拼接 + 时间戳)
    必须和服务端完全一致，包括排序规则和拼接方式
    """
    raw = "".join(f"{k}{body[k]}" for k in sorted(body.keys()))
    return hashlib.md5((key + raw + timestamp).encode()).hexdigest()


def demo_sign_ok():
    print("=" * 60)
    print("2. 实战：算出正确签名并调用（用 assert 断言结果）")
    print("=" * 60)

    body = {"userId": 1, "amount": 100}
    timestamp = str(int(time.time()))
    sign = calc_sign(body, timestamp)

    resp = requests.post(f"{BASE_URL}/api/sign/verify", json=body,
                         headers={"sign": sign, "timestamp": timestamp})
    result = resp.json()
    print(f"  参数：{body}  签名：{sign[:12]}...")
    print(f"  响应：{result}")

    # 两层断言：HTTP 状态码 + 业务 code
    assert resp.status_code == 200, f"HTTP 状态码异常：{resp.status_code}"
    assert result["code"] == 0, f"正确签名却被拒绝：{result}"
    assert result["data"]["msg"] == "验签通过"
    print("  [OK] 断言通过：正确签名 → 服务端放行\n")


# ---------------------------------------------------------------- 3. 反例

def post_sign(body, sign=None, timestamp=None, key=SIGN_KEY):
    """按需要组装请求头，方便构造各种反例"""
    headers = {}
    if sign is not None:
        headers["sign"] = sign
    if timestamp is not None:
        headers["timestamp"] = timestamp
    return requests.post(f"{BASE_URL}/api/sign/verify", json=body, headers=headers)


def demo_sign_fail():
    print("=" * 60)
    print("3. 反例：5 个场景，每个都必须被服务端拒绝（全部断言）")
    print("=" * 60)

    body = {"userId": 1, "amount": 100}
    ts = str(int(time.time()))
    sign = calc_sign(body, ts)

    # ① 参数被篡改（签名用旧参数的，body 换成新的）
    hacked = {"userId": 1, "amount": 999999}
    r = post_sign(hacked, sign=sign, timestamp=ts)
    print(f"  ① 参数被篡改       → code={r.json()['code']} msg={r.json()['msg']}")
    assert r.status_code == 200
    assert r.json()["code"] == 4003, f"参数被篡改却没被拒绝：{r.json()}"
    # 关键：错误信息里【不能】回显正确签名，否则照着改就能绕过验签
    assert "期望" not in r.json()["msg"] and sign[:8] not in r.json()["msg"], \
        f"mock 把正确签名泄露出去了，防篡改形同虚设：{r.json()['msg']}"

    # ② 缺少签名头
    r = post_sign(body, timestamp=ts)
    print(f"  ② 缺少 sign        → code={r.json()['code']} msg={r.json()['msg']}")
    assert r.json()["code"] == 4001, f"缺少签名却没被拒绝：{r.json()}"

    # ③ 时间戳过期（往前推 10 分钟）→ 防重放
    old_ts = str(int(time.time()) - 600)
    r = post_sign(body, sign=calc_sign(body, old_ts), timestamp=old_ts)
    print(f"  ③ 时间戳过期       → code={r.json()['code']} msg={r.json()['msg']}")
    assert r.json()["code"] == 4002, f"过期请求却没被拒绝：{r.json()}"

    # ④ 用错误的密钥算签名（密钥错了，签名必然对不上）
    #    场景：客户端配错密钥 / 调用方被盗用 / 有人重放别家的请求
    wrong_key_sign = calc_sign(body, ts, key="wrong_key_123")
    r = post_sign(body, sign=wrong_key_sign, timestamp=ts)
    print(f"  ④ 密钥错误         → code={r.json()['code']} msg={r.json()['msg']}")
    assert r.json()["code"] == 4003, f"错误密钥的签名却被接受：{r.json()}"

    # ⑤ 相同请求重发两次（防重放：看服务端是否幂等）
    r1 = post_sign(body, sign=sign, timestamp=ts)
    r2 = post_sign(body, sign=sign, timestamp=ts)
    print(f"  ⑤ 同请求重发两次   → 第一次 code={r1.json()['code']}，"
          f"第二次 code={r2.json()['code']}")
    assert r1.json()["code"] == 0
    # 注意：本 mock 只用时间戳做防重放，时间窗内重发仍会通过。
    # 真实支付接口还会带 nonce 或请求流水号，第二次必须被拒。
    # 这里把现状如实断言下来——测试就是要写清楚"当前行为是什么"。
    assert r2.json()["code"] == 0, "mock 行为变了，请同步更新本用例"

    print("\n  这 5 个场景就是签名接口该覆盖的用例集：")
    print("    正确签名 / 参数篡改 / 签名缺失 / 时间戳过期 / 错误密钥 / 重放幂等")
    print("  注意它们全是 HTTP 200，业务结果只体现在 code 上 ——")
    print("  所以只断言 HTTP 状态码的脚本，会把上面 4 个失败全判成 PASS。\n")


# ---------------------------------------------------------------- 4. 超时（语义易错）

def start_drip_server(total_seconds=8, interval=1.0):
    """
    起一个「慢速滴流」服务：先发响应头，然后每 interval 秒吐一点，持续 total_seconds 秒。

    为什么要造这么个服务？
      为了证明 requests 的 timeout **不是**「请求总时长」：
      它只要求「两次收到数据之间的间隔」不超过 read timeout。
      每 1 秒吐一次、总共吐 8 秒的响应，timeout=5 是拦不住的。
    """
    class DripHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            for _ in range(total_seconds):
                self.wfile.write(b'{"tick":1}')
                self.wfile.flush()
                time.sleep(interval)

        def log_message(self, *args):        # 别刷屏
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), DripHandler)   # 端口 0 = 系统随便给一个
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def demo_timeout():
    print("=" * 60)
    print("4. 超时：requests 的 timeout 到底管什么")
    print("=" * 60)

    # 4.1 read timeout：服务端迟迟不吐第一个字节 → 会超时
    print("  【4.1】/api/slow 会睡 3 秒才返回，我们只给 1 秒：")
    try:
        requests.get(f"{BASE_URL}/api/slow", timeout=1)
        raise AssertionError("预期抛 Timeout，但没有——请检查 mock 服务")
    except requests.exceptions.Timeout as e:
        print(f"        抛出 {type(e).__name__}（符合预期：3 秒内一个字节都没收到）")

    # 4.2 关键：单值 timeout 会同时赋给 connect 和 read，read 是「间隔」不是「总时长」
    print("\n  【4.2】慢速滴流服务（每 1 秒吐一次，总共 8 秒），timeout=5：")
    srv, drip_url = start_drip_server(total_seconds=8, interval=1.0)
    try:
        t0 = time.time()
        resp = requests.get(drip_url, timeout=5)
        elapsed = time.time() - t0
    finally:
        srv.shutdown()

    print(f"        结果：HTTP {resp.status_code}，耗时 {elapsed:.1f} 秒")
    assert resp.status_code == 200
    assert elapsed > 5, (
        f"耗时 {elapsed:.1f}s 没有超过 timeout=5，说明本课对 timeout 的解释需要复核")
    print("        → 超过 5 秒了，却没有超时！这证明 timeout 不是「请求总时长」")

    print("\n  【正确理解】")
    print("    timeout=5            等价于 timeout=(5, 5)：")
    print("                           connect=5（建立连接最多 5 秒）")
    print("                           read=5（**两次收到字节之间**最多等 5 秒）")
    print("    timeout=(3, 10)      连接 3 秒，读取间隔 10 秒")
    print("    requests **没有**「整个请求最多 N 秒」这个能力。")
    print("\n  那要控总时长怎么办？")
    print("    ① 用例层自己计时：t0=time.time() ... 断言 elapsed < N")
    print("    ② 换 httpx：它支持 httpx.Timeout(10, connect=3) 这种含 total 的写法")
    print("\n  不设 timeout 的后果：服务端不响应时程序永远卡住，整个测试挂死。\n")


# ---------------------------------------------------------------- 5. 各类异常

def demo_exceptions():
    print("=" * 60)
    print("5. 常见异常与捕获顺序")
    print("=" * 60)

    # 注意：本机若设了 HTTP_PROXY（Clash 这类代理很常见），requests 默认会把
    # 127.0.0.1 的请求也交给代理，于是你拿到的是代理返回的 502，而不是
    # ConnectionError —— 测的就不是「连接被拒」这件事了。必须显式绕开代理。
    DIRECT = {"http": None, "https": None}

    cases = [
        ("连接被拒（服务没起）", "http://127.0.0.1:59999/api",
         {"proxies": DIRECT}, "ConnectionError"),
        ("超时", f"{BASE_URL}/api/slow", {"timeout": 1}, "Timeout"),
    ]

    for name, url, kw, expect in cases:
        try:
            requests.get(url, **kw)
            raise AssertionError(f"{name} 预期抛 {expect}，但没有")
        except requests.exceptions.Timeout:
            actual = "Timeout"
        except requests.exceptions.ConnectionError:
            actual = "ConnectionError"
        except requests.exceptions.RequestException as e:
            actual = type(e).__name__
        print(f"  {name} → {actual}")
        assert actual == expect, f"{name} 期望 {expect}，实际 {actual}"

    print("\n  异常有继承关系，捕获要从具体到宽泛：")
    print("    RequestException（父类）")
    print("      ├── Timeout")
    print("      │     └── ConnectTimeout / ReadTimeout")
    print("      ├── ConnectionError")
    print("      ├── HTTPError（raise_for_status 抛的）")
    print("      └── TooManyRedirects")
    print("\n  写反了（Exception 写最前面）→ 具体分支永远进不去\n")


# ---------------------------------------------------------------- 6. 两层请求封装

def request_transport(method, url, expect_http=200, expect_code=0, **kwargs):
    """
    带两层断言的请求封装 —— 框架里应该这么写

      第一层（传输层）：超时、连接失败、HTTP 状态码不符 → 判失败
      第二层（业务层）：HTTP 通了**不代表业务对**，还要看响应体里的 code

    为什么必须分两层？
      本项目的 mock 除了 401，所有业务失败都是 **HTTP 200 + code != 0**。
      只按 raise_for_status() 判成功的写法，会把「密码错误」「验签失败」
      全部判成 PASS —— 这是最常见的一种"假绿"。

    :param expect_http: 期望的 HTTP 状态码
    :param expect_code: 期望的业务 code；传 None 表示这一层不做断言
    :return: (是否通过, 说明文字)
    """
    kwargs.setdefault("timeout", 10)          # 默认超时，别让一个接口拖垮全部

    # ---- 第一层：传输层
    try:
        resp = requests.request(method, url, **kwargs)
    except requests.exceptions.Timeout:
        return False, "传输层失败：请求超时"
    except requests.exceptions.ConnectionError:
        return False, "传输层失败：连接失败"
    except requests.exceptions.RequestException as e:
        return False, f"传输层失败：{type(e).__name__} - {e}"

    if resp.status_code != expect_http:
        return False, (f"传输层失败：HTTP 状态码期望 {expect_http}，"
                       f"实际 {resp.status_code}（body 前 80 字符 {resp.text[:80]!r}）")

    if expect_code is None:
        return True, f"HTTP {resp.status_code}"

    # ---- 第二层：业务层
    try:
        body = resp.json()
    except ValueError:
        # 服务端吐了 HTML 错误页时，这里必须给出干净的失败信息，
        # 而不是把 JSONDecodeError 抛出去让人以为"框架坏了"
        return False, (f"业务层失败：响应不是合法 JSON（HTTP {resp.status_code}，"
                       f"body 前 80 字符 {resp.text[:80]!r}）")

    if body.get("code") != expect_code:
        return False, (f"业务层失败：code 期望 {expect_code}，"
                       f"实际 {body.get('code')}（msg={body.get('msg')!r}）")

    return True, f"HTTP {resp.status_code} + code {expect_code}"


def demo_two_layer_assert():
    print("=" * 60)
    print("6. 实战：两层断言 —— HTTP 通 ≠ 用例通过")
    print("=" * 60)

    token = {"token": "mock_token_abc123"}
    wrong_login = {"username": "admin", "password": "wrong_pwd"}
    body = {"userId": 1, "amount": 100}
    ts = str(int(time.time()))

    tasks = [
        # (说明, method, path, expect_http, expect_code, kwargs, 是否预期通过)
        ("正常接口", "GET", "/api/users", 200, 0, {"headers": token}, True),
        # 这一条故意制造超时：期待它被判 FAIL，且失败原因来自传输层
        ("超时接口（故意失败）", "GET", "/api/slow", 200, 0, {"timeout": 1}, False),
        ("未授权接口（无 token）", "GET", "/api/user/1", 401, 401, {}, True),
        ("密码错误（HTTP 200，业务失败）", "POST", "/api/login", 200, 1003,
         {"json": wrong_login}, True),
        ("验签失败（HTTP 200，业务失败）", "POST", "/api/sign/verify", 200, 4003,
         {"json": body, "headers": {"sign": "deadbeef", "timestamp": ts}}, True),
    ]

    results = []
    for name, method, path, e_http, e_code, kw, expect_ok in tasks:
        ok, detail = request_transport(method, BASE_URL + path,
                                       expect_http=e_http, expect_code=e_code, **kw)
        results.append((name, ok, detail, expect_ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} —— {detail}")

    # 断言"该通过的通过了、该失败的失败了"，防止演示脚本自己骗自己
    wrong = [(n, ok, want, d) for n, ok, d, want in results if ok != want]
    assert not wrong, f"以上 {len(wrong)} 项的通过/失败与预期不符：{wrong}"

    passed = sum(1 for _, ok, _, _ in results if ok)
    failed = len(results) - passed
    print(f"\n  结果：通过 {passed}，失败 {failed}（失败的那条是故意造的）")
    print("  关键点一：第一条超时后，后面的接口照样跑完了 ——")
    print("           捕获 → 记录 → 继续，不让一个接口拖垮全部。")
    print("  关键点二：第 4、5 项都是 HTTP 200，只判状态码会把它们全误判成 PASS；")
    print("           这就是最常见的「假绿」，必须靠第二层业务断言兜住。\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    demo_what_is_sign()
    demo_sign_ok()
    demo_sign_fail()
    demo_timeout()
    demo_exceptions()
    demo_two_layer_assert()

    print("=" * 60)
    print("完成。记住三句话：")
    print("  1. 设 timeout（但它是 connect/read 两个独立超时，不是总时长）")
    print("  2. HTTP 通 ≠ 业务对，断言必须两层")
    print("  3. 该 assert 的地方别 print —— 不然脚本永远 exit 0")
    print("=" * 60)
