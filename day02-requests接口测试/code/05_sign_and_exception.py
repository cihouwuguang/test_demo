# -*- coding: utf-8 -*-
"""
签名接口与异常场景处理

签名在金融/支付类接口里几乎是标配，你在华为钱包做过的 JWE 签名属于同一类东西。

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/05_sign_and_exception.py
"""
import hashlib
import time

import requests

BASE_URL = "http://127.0.0.1:5000"
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
    print("  注意：签名 ≠ 加密。签名防篡改，加密防窃听，两回事。")
    print("        敏感数据（身份证、银行卡）要加密，HTTPS + 字段级加密。\n")


# ---------------------------------------------------------------- 2. 实现签名

def calc_sign(body: dict, timestamp: str) -> str:
    """
    签名规则：md5(密钥 + 参数按 key 升序拼接 + 时间戳)
    必须和服务端完全一致，包括排序规则和拼接方式
    """
    raw = "".join(f"{k}{body[k]}" for k in sorted(body.keys()))
    return hashlib.md5((SIGN_KEY + raw + timestamp).encode()).hexdigest()


def demo_sign_ok():
    print("=" * 60)
    print("2. 实战：算出正确签名并调用")
    print("=" * 60)

    body = {"userId": 1, "amount": 100}
    timestamp = str(int(time.time()))

    sign = calc_sign(body, timestamp)
    print(f"  参数：{body}")
    print(f"  时间戳：{timestamp}")
    print(f"  签名：{sign}")

    resp = requests.post(f"{BASE_URL}/api/sign/verify", json=body,
                         headers={"sign": sign, "timestamp": timestamp})
    print(f"  响应：{resp.json()}\n")


# ---------------------------------------------------------------- 3. 反例

def demo_sign_fail():
    print("=" * 60)
    print("3. 反例：参数被篡改 / 缺少字段 / 请求过期")
    print("=" * 60)

    body = {"userId": 1, "amount": 100}
    timestamp = str(int(time.time()))
    sign = calc_sign(body, timestamp)

    print("  ① 参数被篡改（amount 改成 999999，签名没重算）：")
    hacked = {"userId": 1, "amount": 999999}
    r = requests.post(f"{BASE_URL}/api/sign/verify", json=hacked,
                      headers={"sign": sign, "timestamp": timestamp})
    print(f"     响应：{r.json()['msg']}\n")

    print("  ② 缺少签名头：")
    r = requests.post(f"{BASE_URL}/api/sign/verify", json=body)
    print(f"     响应：{r.json()['msg']}\n")

    print("  ③ 请求过期（时间戳往前推 10 分钟）：")
    old_ts = str(int(time.time()) - 600)
    old_sign = calc_sign(body, old_ts)
    r = requests.post(f"{BASE_URL}/api/sign/verify", json=body,
                      headers={"sign": old_sign, "timestamp": old_ts})
    print(f"     响应：{r.json()['msg']}    ← 这就是防重放\n")

    print("  测试用例设计（这就是签名接口要覆盖的场景）：")
    print("    - 正确签名 → 通过")
    print("    - 参数篡改 → 拒绝")
    print("    - 签名缺失/为空 → 拒绝")
    print("    - 时间戳过期 → 拒绝")
    print("    - 相同请求重发两次 → 看是否幂等\n")


# ---------------------------------------------------------------- 4. 超时

def demo_timeout():
    print("=" * 60)
    print("4. 超时处理")
    print("=" * 60)

    print("  /api/slow 会睡 3 秒，我们只给 1 秒：")
    try:
        requests.get(f"{BASE_URL}/api/slow", timeout=1)
        print("    居然成功了")
    except requests.exceptions.Timeout:
        print("    捕获 Timeout（符合预期）")
    except requests.exceptions.RequestException as e:
        print(f"    捕获其他异常：{type(e).__name__}")

    print("\n  timeout 的两种写法：")
    print("    timeout=5          总共 5 秒（连接 + 读取）")
    print("    timeout=(3, 10)    连接 3 秒，读取 10 秒")
    print("\n  不设 timeout 的后果：服务端不响应时程序永远卡住，整个测试挂死\n")


# ---------------------------------------------------------------- 5. 各类异常

def demo_exceptions():
    print("=" * 60)
    print("5. 常见异常与捕获顺序")
    print("=" * 60)

    cases = [
        ("连接被拒（服务没起）", "http://127.0.0.1:59999/api", {}),
        ("超时", f"{BASE_URL}/api/slow", {"timeout": 1}),
    ]

    for name, url, kw in cases:
        try:
            requests.get(url, **kw)
        except requests.exceptions.Timeout:
            print(f"  {name} → Timeout")
        except requests.exceptions.ConnectionError:
            print(f"  {name} → ConnectionError")
        except requests.exceptions.RequestException as e:
            print(f"  {name} → {type(e).__name__}")

    print("\n  异常有继承关系，捕获要从具体到宽泛：")
    print("    RequestException（父类）")
    print("      ├── Timeout")
    print("      │     └── ConnectTimeout / ReadTimeout")
    print("      ├── ConnectionError")
    print("      ├── HTTPError（raise_for_status 抛的）")
    print("      └── TooManyRedirects")
    print("\n  写反了（Exception 写最前面）→ 具体分支永远进不去\n")


# ---------------------------------------------------------------- 6. 统一请求封装

def safe_request(method, url, **kwargs):
    """
    带容错的请求封装：框架里就该这么写
    返回 (是否成功, 响应对象或错误信息)
    """
    kwargs.setdefault("timeout", 10)      # 默认超时
    try:
        resp = requests.request(method, url, **kwargs)
        resp.raise_for_status()
        return True, resp
    except requests.exceptions.Timeout:
        return False, f"请求超时：{url}"
    except requests.exceptions.ConnectionError:
        return False, f"连接失败：{url}"
    except requests.exceptions.HTTPError as e:
        return False, f"HTTP 错误：{e}"
    except requests.exceptions.RequestException as e:
        return False, f"请求异常：{type(e).__name__} - {e}"


def demo_safe_request():
    print("=" * 60)
    print("6. 实战：一个接口挂了，不能让整个测试崩掉")
    print("=" * 60)

    tasks = [
        ("正常接口", "GET", f"{BASE_URL}/api/users", {"headers": {"token": "mock_token_abc123"}}),
        ("超时接口", "GET", f"{BASE_URL}/api/slow", {"timeout": 1}),
        ("报错接口", "GET", f"{BASE_URL}/api/error", {}),
        ("正常接口2", "GET", f"{BASE_URL}/api/user/1", {"headers": {"token": "mock_token_abc123"}}),
    ]

    passed, failed = 0, []
    for name, method, url, kw in tasks:
        ok_, result = safe_request(method, url, **kw)
        if ok_:
            print(f"  [PASS] {name}")
            passed += 1
        else:
            print(f"  [FAIL] {name} —— {result}")
            failed.append(name)

    print(f"\n  结果：通过 {passed}，失败 {len(failed)} —— {failed}")
    print("  关键点：第二个接口失败后，第三第四个照样跑完了")
    print("         这就是框架要做的：捕获 → 记录 → 继续\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    demo_what_is_sign()
    demo_sign_ok()
    demo_sign_fail()
    demo_timeout()
    demo_exceptions()
    demo_safe_request()

    print("=" * 60)
    print("完成。记住：设 timeout、捕获异常、记录继续，不让一个接口拖垮全部")
    print("=" * 60)
