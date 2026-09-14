# -*- coding: utf-8 -*-
"""
面向对象：类、继承、封装 —— 框架分层的基础

本文件不真的发请求，只用 print 模拟，目的是让你专注理解"类"本身。
Day 4 会把这里的结构换成真的 requests。

运行：python day01-Python核心/code/03_oop.py
"""
import functools
import time


# ---------------------------------------------------------------- 1. 为什么需要类

def demo_why_class():
    print("=" * 60)
    print("1. 不用类有多痛，用了类有多爽")
    print("=" * 60)

    print("  不用类：10 个用户要 30 个变量")
    user1_name, user1_phone = "admin", "138..."
    user2_name, user2_phone = "tester", "139..."
    print(f"    {user1_name} / {user2_name}")

    print("\n  用类：一个模板造任意多个")
    class User:
        def __init__(self, name, phone):
            self.name = name
            self.phone = phone

    u1 = User("admin", "138...")
    u2 = User("tester", "139...")
    print(f"    {u1.name} / {u2.name}")
    print("  结论：类是图纸，实例是按图纸造出来的东西\n")


# ---------------------------------------------------------------- 2. self 是什么

def demo_self():
    print("=" * 60)
    print("2. self 到底是什么")
    print("=" * 60)

    class User:
        def __init__(self, name):
            print(f"    __init__ 被调用，self 是 {id(self)}")
            self.name = name

    u = User("admin")
    print(f"    u = User(...) 之后，u 是 {id(u)}")
    print("    两个 id 一样 → self 就是当前这个实例")
    print("    所以 u.name 和 self.name 是同一个东西\n")


# ---------------------------------------------------------------- 3. 类属性 vs 实例属性

def demo_attr():
    print("=" * 60)
    print("3. 类属性 vs 实例属性（经典坑）")
    print("=" * 60)

    class Config:
        env = "test"              # 类属性：所有实例共享
        def __init__(self, name):
            self.name = name      # 实例属性：各管各的

    a = Config("A")
    b = Config("B")

    print(f"  初始：a.name={a.name}, b.name={b.name}")
    print(f"  初始：a.env={a.env}, b.env={b.env}")

    Config.env = "prod"
    print(f"\n  执行 Config.env = 'prod' 后：")
    print(f"    a.env={a.env}, b.env={b.env}    ← 全都变了（共享）")

    a.name = "AAA"
    print(f"\n  执行 a.name = 'AAA' 后：")
    print(f"    a.name={a.name}, b.name={b.name}    ← 只有 a 变（独立）")
    print("  框架里就利用这一点：base_url 放类属性，改一处全局生效\n")


# ---------------------------------------------------------------- 4. 方法之间共享状态

def demo_shared_state():
    print("=" * 60)
    print("4. 类最大的价值：方法之间共享状态")
    print("=" * 60)

    class UserAPI:
        def __init__(self):
            self.token = None

        def login(self, username, password):
            print(f"    登录 {username}，拿到 token")
            self.token = "mock_token_abc123"     # 存到实例上
            return self.token

        def get_user(self, uid):
            print(f"    用 token={self.token} 查询用户 {uid}")   # 别的方法直接用

    api = UserAPI()
    api.login("admin", "123456")
    api.get_user(1)
    print("  不用类的话，token 只能传来传去或者用全局变量（很脏）\n")


# ---------------------------------------------------------------- 5. 继承（重点）

def demo_inheritance():
    print("=" * 60)
    print("5. 继承：公共代码抽到父类（Day 4 分层的核心）")
    print("=" * 60)

    class BaseAPI:
        """父类：只放公共能力"""
        base_url = "http://127.0.0.1:5000"     # 类属性

        def request(self, method, path, **kwargs):
            url = self.base_url + path
            print(f"    [父类] 请求 {method} {url}，参数 {kwargs}")
            print(f"    [父类] 记录日志、处理超时、捕获异常")
            return {"code": 0, "msg": "success", "url": url}

    class UserAPI(BaseAPI):
        """子类：只写业务"""
        def login(self, username, password):
            return self.request("POST", "/api/login",
                                json={"username": username, "password": password})

        def get_user(self, uid):
            return self.request("GET", f"/api/user/{uid}")

    class OrderAPI(BaseAPI):
        def create_order(self, user_id, amount):
            return self.request("POST", "/api/order",
                                json={"userId": user_id, "amount": amount})

    user_api = UserAPI()
    order_api = OrderAPI()

    print("  调用 UserAPI.login：")
    user_api.login("admin", "123456")
    print("\n  调用 OrderAPI.create_order：")
    order_api.create_order(1, 99.9)
    print("\n  请求逻辑、日志只在父类写了一次，两个子类都享受到了")
    print("  要加'统一超时'，只改父类一处\n")


# ---------------------------------------------------------------- 6. super()

def demo_super():
    print("=" * 60)
    print("6. super()：先执行父类的，再加自己的")
    print("=" * 60)

    class BaseAPI:
        def __init__(self):
            self.base_url = "http://127.0.0.1:5000"
            self.session = "模拟的 Session"

    class UserAPI(BaseAPI):
        def __init__(self):
            super().__init__()          # 先跑父类的初始化
            self.token = None           # 再加自己的

    api = UserAPI()
    print(f"  继承自父类的 base_url：{api.base_url}")
    print(f"  继承自父类的 session： {api.session}")
    print(f"  自己的 token：         {api.token}")
    print("  不写 super().__init__() 的话，父类的属性就没了\n")


# ---------------------------------------------------------------- 7. 魔术方法

def demo_magic():
    print("=" * 60)
    print("7. 魔术方法：让 print(对象) 好看点")
    print("=" * 60)

    class UserNoStr:
        def __init__(self, name):
            self.name = name

    class User:
        def __init__(self, name):
            self.name = name
        def __str__(self):
            return f"用户({self.name})"

    print(f"  没有 __str__：{UserNoStr('admin')}")
    print(f"  有 __str__：  {User('admin')}")
    print("  调试时差别很大，框架里的响应对象一般都会加\n")


# ---------------------------------------------------------------- 8. 用装饰器装饰类的方法

def timer(func):
    @functools.wraps(func)
    def inner(*args, **kwargs):
        start = time.time()
        r = func(*args, **kwargs)
        print(f"    [{func.__name__}] 耗时 {time.time() - start:.3f} 秒")
        return r
    return inner


class Calculator:
    @timer
    def add(self, a, b):
        time.sleep(0.1)
        return a + b


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    demo_why_class()
    demo_self()
    demo_attr()
    demo_shared_state()
    demo_inheritance()
    demo_super()
    demo_magic()

    print("=" * 60)
    print("8. 装饰器 + 类：给方法加计时")
    print("=" * 60)
    c = Calculator()
    print(f"  1 + 2 = {c.add(1, 2)}\n")

    print("=" * 60)
    print("完成。记住：公共的放父类，业务的放子类")
    print("=" * 60)
