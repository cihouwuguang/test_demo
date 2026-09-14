# -*- coding: utf-8 -*-
"""
装饰器：从最朴素写法到实战用法

运行：python day01-Python核心/code/01_decorator.py
"""
import time
import functools


# ---------------------------------------------------------------- 1. 函数也是对象

def demo_func_is_object():
    print("=" * 60)
    print("1. 函数在 Python 里是'东西'，可以被传来传去")
    print("=" * 60)

    def hello():
        print("    你好")

    a = hello          # 不带括号：把函数本身赋给 a
    print("  赋值 a = hello 后，调用 a()：")
    a()

    def run(func):     # 函数可以作为参数
        print("  run 收到一个函数，开始调用它：")
        func()

    run(hello)
    print("  结论：hello 是'东西'，hello() 是'执行'\n")


# ---------------------------------------------------------------- 2. 闭包

def demo_closure():
    print("=" * 60)
    print("2. 闭包：内层函数记住了外层变量")
    print("=" * 60)

    def outer():
        msg = "我是外层变量"
        def inner():
            print(f"    inner 里还能用到外层变量：{msg}")
        return inner       # 返回函数本身（不带括号）

    f = outer()
    print("  outer() 已经执行完了，但调用 f()：")
    f()
    print("  结论：msg 被 inner 记住了，这就是闭包\n")


# ---------------------------------------------------------------- 3. 手写装饰器（朴素版）

def demo_decorator_manual():
    print("=" * 60)
    print("3. 不用 @ 语法，手动包装一遍")
    print("=" * 60)

    def log_wrapper(func):
        def inner():
            print("    === 开始执行 ===")
            func()
            print("    === 执行结束 ===")
        return inner

    def login():
        print("    执行登录逻辑")

    print("  手动包装：login = log_wrapper(login)")
    login = log_wrapper(login)
    login()
    print("  结论：装饰器的本质就是这句赋值\n")


# ---------------------------------------------------------------- 4. @ 语法糖

def log_wrapper(func):
    @functools.wraps(func)          # 保留原函数的名字和文档
    def inner(*args, **kwargs):
        print(f"    === 开始执行 {func.__name__} ===")
        result = func(*args, **kwargs)
        print(f"    === {func.__name__} 执行结束 ===")
        return result
    return inner


def demo_syntax_sugar():
    print("=" * 60)
    print("4. @ 就是语法糖，等价于 login = log_wrapper(login)")
    print("=" * 60)

    @log_wrapper
    def login(username, pwd):
        print(f"    登录：{username} / {pwd}")
        return "token_xxx"

    r = login("admin", "123456")
    print(f"  返回值：{r}")
    print(f"  函数名还是原来的吗？{login.__name__}")
    print("  结论：@ 让包装这件事看起来更自然\n")


# ---------------------------------------------------------------- 5. wraps 的作用

def demo_wraps():
    print("=" * 60)
    print("5. functools.wraps 加与不加的区别")
    print("=" * 60)

    def no_wraps(func):
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
        return inner

    def with_wraps(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)
        return inner

    @no_wraps
    def f1():
        pass

    @with_wraps
    def f2():
        pass

    print(f"  不加 wraps：f1.__name__ = {f1.__name__}")
    print(f"  加了 wraps：f2.__name__ = {f2.__name__}")
    print("  结论：不加的话日志里全是 inner，排查问题时看不出是谁\n")


# ---------------------------------------------------------------- 6. 实战：计时装饰器

def timer(func):
    """统计函数运行时间（面试高频手写题）"""
    @functools.wraps(func)
    def inner(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        cost = time.time() - start
        print(f"    [{func.__name__}] 耗时 {cost:.3f} 秒")
        return result
    return inner


@timer
def slow_task(seconds):
    time.sleep(seconds)
    return "完成"


# ---------------------------------------------------------------- 7. 带参数的装饰器

def retry(times=3, delay=0.1):
    """失败自动重试（三层装饰器）"""
    def decorator(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            last_exc = None
            for i in range(times):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    print(f"    第 {i + 1} 次失败：{e}")
                    if i < times - 1:
                        time.sleep(delay)
            print(f"    重试 {times} 次仍失败，抛出异常")
            raise last_exc
        return inner
    return decorator


_fail_count = 0


@retry(times=3, delay=0.1)
def unstable_api():
    """前两次故意失败，第三次成功"""
    global _fail_count
    _fail_count += 1
    if _fail_count < 3:
        raise ConnectionError("模拟网络抖动")
    return "调用成功"


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    demo_func_is_object()
    demo_closure()
    demo_decorator_manual()
    demo_syntax_sugar()
    demo_wraps()

    print("=" * 60)
    print("6. 实战：计时装饰器")
    print("=" * 60)
    print(f"  返回结果：{slow_task(0.5)}\n")

    print("=" * 60)
    print("7. 带参数的装饰器：失败重试")
    print("=" * 60)
    print(f"  最终结果：{unstable_api()}\n")

    print("=" * 60)
    print("完成。思考：为什么 pytest 的 fixture 要用装饰器？")
    print("=" * 60)
