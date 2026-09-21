# -*- coding: utf-8 -*-
"""
数据库校验：接口返回成功，不代表数据真的落库了

用 Python 内置的 sqlite3 演示（不用装东西）。
实际项目里 MySQL 用 pymysql，写法几乎一样，区别在注释里标了。

[!] **本课的一个重要前提，必须先说清楚**：
    课程配套的 mock 服务（`mock_server/app.py`）没有数据库，订单存在内存字典里。
    所以本文件里的"落库"这一步是**脚本自己代替被测系统做的**（标了【替身】）。
    它演示的是**数据库校验的写法**，不是"我真的发现了一个没落库的 bug"。
    面试被问到时照实说，别说成"我测出过落库失败的问题"。

    要在本地看到真正的"接口成功但没落库"，得让被测系统自己维护持久化存储——
    那超出这门 5 天冲刺课的范围，知道套路和写法就够用了。

[!] **另一个坑**：本文件用裸 `assert` 教学，但 `python -O xxx.py` 会把所有 assert
    全部编译掉（`__debug__` 为假），脚本会一路"通过"。做严肃测试时用
    pytest / unittest 的断言，或者显式 `if not cond: raise AssertionError(...)`。
    这里保留 assert 是为了让写法更直观，但你必须知道这个开关的存在。

前置：先启动 mock 服务
    python mock_server/app.py

运行：python day02-requests接口测试/code/04_db_check.py
"""
import os
import sqlite3
import tempfile
from decimal import Decimal

import requests

BASE_URL = "http://127.0.0.1:5000"

# 本机地址必须绕过系统代理：开着代理软件时 requests 会把 127.0.0.1 的请求
# 也发去代理，代理一不在，本脚本所有请求立刻失败，报错却像"服务没启动"。
# 真实项目推荐在系统环境变量里设 NO_PROXY=127.0.0.1,localhost。
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
DB_PATH = os.path.join(tempfile.gettempdir(), "aa_demo.db")


def check_server():
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.RequestException:
        print("错误：连不上 mock 服务，请先执行 python mock_server\\app.py")
        raise SystemExit(1)


def init_db():
    """建表。真实项目里这一步是开发做的，测试只负责查。"""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE orders (
            order_id     INTEGER PRIMARY KEY,
            user_id      INTEGER,
            goods_name   TEXT,
            -- 金额以「分」为单位存整数，从根上避免浮点精度问题
            -- （本课第 4 节会讲为什么不能用 float / TEXT 存金额）
            amount_cents INTEGER,
            status       TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print(f"  建表完成：{DB_PATH}")


# ---------------------------------------------------------------- 1. 基本操作

def demo_basic_sql():
    print("=" * 60)
    print("1. Python 操作数据库的基本套路")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 增（注意金额存的是分：99.90 元 → 9990 分）
    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                (1001, 1, "测试商品", 9990, "CREATED"))
    conn.commit()          # 增删改必须 commit，查询不用
    print("  插入一条订单（金额 99.90 元，存 9990 分）")

    # 查一条
    cur.execute("SELECT * FROM orders WHERE order_id = ?", (1001,))
    print(f"  fetchone：{cur.fetchone()}")

    # 查所有
    cur.execute("SELECT * FROM orders")
    print(f"  fetchall：{cur.fetchall()}")

    # 改
    cur.execute("UPDATE orders SET status = ? WHERE order_id = ?", ("PAID", 1001))
    conn.commit()
    cur.execute("SELECT status FROM orders WHERE order_id = ?", (1001,))
    print(f"  更新后状态：{cur.fetchone()[0]}")

    # 删
    cur.execute("DELETE FROM orders WHERE order_id = ?", (1001,))
    conn.commit()
    print("  删除完成")

    cur.close()
    conn.close()

    print("\n  要点：")
    print("    - 参数用 ? 占位（MySQL 的 pymysql 用 %s），不要字符串拼接")
    print("    - 增删改要 conn.commit()，查询不用")
    print("    - 用完 cur.close() 和 conn.close()")
    print("    - MySQL 版：import pymysql; conn = pymysql.connect(host=..., user=..., password=..., db=...)\n")


# ---------------------------------------------------------------- 2. 为什么要查库

def demo_why():
    print("=" * 60)
    print("2. 为什么接口返回成功还要查库？")
    print("=" * 60)

    print("  真实 bug 长这样：")
    print("    接口返回：{'code': 0, 'msg': '下单成功'}")
    print("    数据库：  orders 表里空空如也")
    print()
    print("  可能原因：")
    print("    ① 事务回滚了，但异常被吞掉没往上抛")
    print("    ② 异步落库，写入失败但接口先返回了")
    print("    ③ 只改了缓存/Redis，没同步到数据库")
    print("    ④ 数据库字段长度不够，插入被截断或失败")
    print()
    print("  结论：金融类业务（下单、支付、核销、发券）必须做库表校验")
    print("        注意：这类 bug **只有查库才能发现**，接口断言一定看不出来——")
    print("        因为接口返回的一切都是对的，错的是「数据没落地」。\n")


# ---------------------------------------------------------------- 3. 完整校验

def query_order(cur, order_id):
    """查库：真实项目里测试只做这一步，数据是系统写进去的"""
    cur.execute("SELECT status, amount_cents FROM orders WHERE order_id = ?", (order_id,))
    return cur.fetchone()


def check_order(cur, order_id, expect_status, expect_amount_cents):
    """
    这就是「数据库校验」的写法：查出来 → 逐项断言 → 失败信息带上下文

    这个函数才是本课的主角。注意它**不负责写数据**——
    写数据是被测系统的事，测试只负责"我信不过你，我自己去库里看一眼"。
    """
    row = query_order(cur, order_id)
    assert row is not None, \
        f"数据库里没查到订单 {order_id}！接口说成功了，但库里没有"
    assert row[0] == expect_status, \
        f"订单 {order_id} 状态不对：库里是 {row[0]!r}，期望 {expect_status!r}"
    assert row[1] == expect_amount_cents, \
        f"订单 {order_id} 金额不对：库里是 {row[1]} 分，期望 {expect_amount_cents} 分"


def demo_full_check():
    print("=" * 60)
    print("3. 实战：调接口 → 落库 → 查库校验")
    print("=" * 60)

    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/login",
                  json={"username": "admin", "password": "123456"})
    s.headers.update({"token": resp.json()["data"]["token"]})

    # ① 调下单接口
    amount = 128.50
    amount_cents = int(round(amount * 100))          # 128.50 元 → 12850 分
    r = s.post(f"{BASE_URL}/api/order",
               json={"userId": 1, "amount": amount, "goodsName": "接口下单"})
    order_id = r.json()["data"]["orderId"]
    print(f"  ① 调接口下单成功，orderId={order_id}")
    print(f"     接口返回：{r.json()['data']}")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # ② 【替身】真实项目里这一步由被测系统完成，测试不参与
    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                (order_id, 1, "接口下单", amount_cents, "CREATED"))
    conn.commit()
    print("  ② 【替身】把订单写进库（真实场景下是系统自己写的，测试不参与）")

    # ③ 查库校验 —— 这才是测试真正做的事
    check_order(cur, order_id, "CREATED", amount_cents)
    row = query_order(cur, order_id)
    print(f"  ③ 查库结果：{row}  →  三项断言全部通过")

    # ④ 反面演示：这个断言真的会失败吗？
    #
    #    很多人写的是「自证式断言」：脚本自己插一条数据，
    #    紧接着断言"我插的这条数据等于我插的值"。这种断言**永远不可能失败**，
    #    也就永远不可能因为"系统没落库"而报警 —— 它测的是脚本自己。
    #
    #    所以这里故意用一个**错误的期望值**去调同一个断言，
    #    验证它真的会炸。会炸，才说明前面那条"通过"是有意义的。
    print("\n  ④ 反面演示：故意断言一个错的状态，看断言是否真的会失败")
    try:
        check_order(cur, order_id, "PAID", amount_cents)
    except AssertionError as e:
        print(f"     断言如期失败 [OK]  {e}")
    else:
        raise SystemExit("断言本该失败却通过了 —— 说明校验逻辑是假的，必须排查")

    cur.close()
    conn.close()
    print()


# ---------------------------------------------------------------- 4. 金额精度

def demo_decimal():
    print("=" * 60)
    print("4. 金额为什么不能直接用 == 比较，也不该用 TEXT 存")
    print("=" * 60)

    print(f"  0.1 + 0.2 = {0.1 + 0.2}")
    print(f"  0.1 + 0.2 == 0.3 ？ {0.1 + 0.2 == 0.3}    ← 是 False！")
    print()
    print("  原因：二进制浮点数无法精确表示 0.1 这样的十进制小数")
    print()

    print("  解法一：用 Decimal")
    print(f"    Decimal('0.1') + Decimal('0.2') == Decimal('0.3') ？ "
          f"{Decimal('0.1') + Decimal('0.2') == Decimal('0.3')}")

    print("  解法二：比较差值（±0.01 以内算相等）")
    print(f"    abs(0.1+0.2-0.3) < 0.01 ？ {abs(0.1 + 0.2 - 0.3) < 0.01}")

    print("  解法三（推荐）：以分为单位存整数")
    print("    128.50 元 → 存 12850 分，整数比较永不丢精度")
    print("    ← 本文件的 orders 表就是这么建的（amount_cents INTEGER）")
    print()

    print("  为什么也不要用 TEXT 存金额？")
    print("    ① 排序会按字符串排，'9.00' > '10.00'，报表直接错")
    print("    ② 没法在库里做 SUM/AVG 这类聚合")
    print("    ③ '99.9' 和 '99.90' 会被当成两个不同的值，去重/比对全乱")
    print()

    print("  面试说法：")
    print("    金额字段数据库用 DECIMAL 类型，代码里用 Decimal 类，")
    print("    或者以分为单位存整数。绝不用 float，也不要用字符串。\n")


# ---------------------------------------------------------------- 5. 数据清理

def demo_cleanup():
    print("=" * 60)
    print("5. 别忘了一件大事：测完要清理数据")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    before = cur.fetchone()[0]
    print(f"  清理前订单数：{before}")

    cur.execute("DELETE FROM orders")
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM orders")
    after = cur.fetchone()[0]
    print(f"  清理后订单数：{after}")

    cur.close()
    conn.close()

    print("\n  为什么重要：")
    print("    - 脏数据会让下次测试失败（比如下单用了重复的单号）")
    print("    - 测试环境数据越堆越多，最后没人敢用")
    print("    - 框架里一般用 fixture 的 teardown 自动清理（Day 3 讲）")
    print("    - [!] 清理不要依赖前置用例成功：")
    print("      Day4 框架里「删除刚创建的用户」依赖「创建用户成功」提取的变量，")
    print("      前置一失败就会留下脏数据 —— 所以那里额外做了兜底清理。\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    check_server()
    init_db()
    demo_basic_sql()
    demo_why()
    demo_full_check()
    demo_decimal()
    demo_cleanup()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=" * 60)
    print("完成。记住：接口成功 + 数据落库，两个都验证了才算真的通过")
    print("=" * 60)
