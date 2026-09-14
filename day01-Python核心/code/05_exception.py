# -*- coding: utf-8 -*-
"""
异常处理：框架里为什么一个接口挂了不能让整个测试跑崩

运行：python day01-Python核心/code/05_exception.py
"""


# ---------------------------------------------------------------- 1. 基本结构

def demo_basic():
    print("=" * 60)
    print("1. try / except / else / finally")
    print("=" * 60)

    # 没异常的情况
    try:
        result = 10 / 2
    except ZeroDivisionError:
        print("    除零了")
    else:
        print(f"    没出异常，走 else：结果 {result}")
    finally:
        print("    走 finally：无论是否异常都会执行")

    # 有异常的情况
    print()
    try:
        result = 10 / 0
    except ZeroDivisionError as e:
        print(f"    捕获到异常：{e}")
    else:
        print("    不会走这里")
    finally:
        print("    走 finally：通常用来关连接、关文件")

    print("\n  要点：")
    print("    - else 是'没异常才执行'，不是必须写的")
    print("    - finally 一定执行，即使前面 return 了\n")


# ---------------------------------------------------------------- 2. 捕获顺序

def demo_order():
    print("=" * 60)
    print("2. 捕获顺序：从具体到宽泛（写反了就永远抓不到）")
    print("=" * 60)

    print("  错误示范：把 Exception 写在最前面")
    try:
        int("abc")
    except Exception:
        print("    被 Exception 拦截了，具体异常永远轮不到")

    print("\n  正确示范：具体的写前面")
    try:
        int("abc")
    except ValueError as e:
        print(f"    先抓 ValueError：{e}")
    except Exception as e:
        print(f"    再抓通用 Exception：{e}")

    print("\n  结论：子类异常必须写在父类前面\n")


# ---------------------------------------------------------------- 3. 自定义异常

class ApiException(Exception):
    """自定义异常：接口断言失败时抛这个"""
    def __init__(self, msg, resp=None):
        super().__init__(msg)
        self.msg = msg
        self.resp = resp


def call_api(status_code):
    if status_code != 200:
        raise ApiException(f"接口返回异常状态码 {status_code}", resp=status_code)
    return {"code": 0, "data": "ok"}


def demo_custom():
    print("=" * 60)
    print("3. 自定义异常：让失败信息更清晰")
    print("=" * 60)

    try:
        call_api(500)
    except ApiException as e:
        print(f"    捕获自定义异常：{e.msg}")
        print(f"    还能带上原始响应：{e.resp}")

    print("\n  框架里这么用：断言失败抛异常 → 上层捕获 → 记日志 → 标记用例失败")
    print("  而不是让整个测试直接崩掉\n")


# ---------------------------------------------------------------- 4. 实战：不中断的批量执行

def demo_batch():
    print("=" * 60)
    print("4. 实战：一条用例失败，不影响后面的继续跑")
    print("=" * 60)

    cases = [
        ("正常用例", lambda: {"code": 0}),
        ("会报错的用例", lambda: (_ for _ in ()).throw(ConnectionError("连接失败"))),
        ("后面的用例", lambda: {"code": 0}),
    ]

    passed, failed = 0, []
    for name, action in cases:
        try:
            action()
            print(f"    [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"    [FAIL] {name} —— {e}")
            failed.append(name)

    print(f"\n  结果：通过 {passed}，失败 {len(failed)} —— {failed}")
    print("  框架的核心思想就是这个：捕获异常、记录、继续\n")


# ---------------------------------------------------------------- 5. 常见异常类型

def demo_types():
    print("=" * 60)
    print("5. 做自动化最常遇到的异常")
    print("=" * 60)

    demos = [
        ("KeyError", lambda: {}["不存在的key"]),
        ("IndexError", lambda: [1, 2, 3][10]),
        ("TypeError", lambda: 1 + "1"),
        ("AttributeError", lambda: "abc".not_exist_method()),
        ("ValueError", lambda: int("abc")),
        ("FileNotFoundError", lambda: open("不存在的文件.txt")),
    ]

    for name, action in demos:
        try:
            action()
        except Exception as e:
            print(f"    {type(e).__name__}：{e}")

    print("\n  排查口诀：看错误信息的最后一行，类型和原因都写在那里\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    demo_basic()
    demo_order()
    demo_custom()
    demo_batch()
    demo_types()

    print("=" * 60)
    print("完成。记住：捕获 → 记录 → 继续，不要让整个测试崩掉")
    print("=" * 60)
