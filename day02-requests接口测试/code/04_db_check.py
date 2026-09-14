# -*- coding: utf-8 -*-
"""
数据库校验：接口返回成功，不代表数据真的落库了

用 Python 内置的 sqlite3 演示（不用装东西）。
实际项目里 MySQL 用 pymysql，写法几乎一样，区别在注释里标了。

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
            order_id   INTEGER PRIMARY KEY,
            user_id    INTEGER,
            goods_name TEXT,
            amount     TEXT,
            status     TEXT
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

    # 增
    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                (1001, 1, "测试商品", "99.90", "CREATED"))
    conn.commit()          # 增删改必须 commit，查询不用
    print("  插入一条订单")

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
    print("  结论：金融类业务（下单、支付、核销、发券）必须做库表校验\n")


# ---------------------------------------------------------------- 3. 完整校验

def demo_full_check():
    print("=" * 60)
    print("3. 实战：调接口 → 落库 → 查库校验")
    print("=" * 60)

    s = requests.Session()
    resp = s.post(f"{BASE_URL}/api/login",
                  json={"username": "admin", "password": "123456"})
    s.headers.update({"token": resp.json()["data"]["token"]})

    # 调下单接口
    amount = 128.50
    r = s.post(f"{BASE_URL}/api/order",
               json={"userId": 1, "amount": amount, "goodsName": "接口下单"})
    order_id = r.json()["data"]["orderId"]
    print(f"  ① 调接口下单成功，orderId={order_id}")
    print(f"     接口返回：{r.json()['data']}")

    # 模拟落库（真实项目里这一步由被测系统完成）
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                (order_id, 1, "接口下单", f"{amount:.2f}", "CREATED"))
    conn.commit()
    print(f"  ② 数据落库（真实场景下是系统自己写的）")

    # 查库校验
    cur.execute("SELECT status, amount FROM orders WHERE order_id = ?", (order_id,))
    row = cur.fetchone()
    print(f"  ③ 查库结果：{row}")

    # 断言
    assert row is not None, f"数据库里没查到订单 {order_id}！"
    assert row[0] == "CREATED", f"订单状态不对，期望 CREATED，实际 {row[0]}"
    assert abs(Decimal(row[1]) - Decimal(str(amount))) < Decimal("0.01"), \
        f"金额不对，期望 {amount}，实际 {row[1]}"
    print("  ④ 三项断言全部通过")

    cur.close()
    conn.close()
    print()


# ---------------------------------------------------------------- 4. 金额精度

def demo_decimal():
    print("=" * 60)
    print("4. 金额为什么不能直接用 == 比较")
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
    print()

    print("  面试说法：")
    print("    金额字段数据库用 DECIMAL 类型，代码里用 Decimal 类，")
    print("    或者以分为单位存整数。绝不用 float。\n")


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
    print("    - 框架里一般用 fixture 的 teardown 自动清理（Day 3 讲）\n")


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
