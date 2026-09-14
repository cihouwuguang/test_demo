# -*- coding: utf-8 -*-
"""
yield 与生成器：pytest 前后置的原理就在这

运行：python day01-Python核心/code/02_yield.py
"""
import sys
from contextlib import contextmanager


# ---------------------------------------------------------------- 1. return vs yield

def demo_return_vs_yield():
    print("=" * 60)
    print("1. return 和 yield 的第一眼区别")
    print("=" * 60)

    def with_return():
        return 1
        return 2          # 永远执行不到

    def with_yield():
        yield 1
        yield 2
        yield 3

    print(f"  with_return() 的结果：{with_return()}")
    print(f"  with_yield()  的结果：{with_yield()}")
    print("  注意：with_yield() 返回的是生成器对象，不是 1")
    print("  说明调用时函数体一行都没执行\n")


# ---------------------------------------------------------------- 2. next 逐个取

def demo_next():
    print("=" * 60)
    print("2. 用 next() 一个个取，函数边走边停")
    print("=" * 60)

    def counter():
        print("    [函数内部] 准备产出 1")
        yield 1
        print("    [函数内部] 准备产出 2")
        yield 2
        print("    [函数内部] 准备产出 3")
        yield 3
        print("    [函数内部] 没有更多了")

    g = counter()
    print("  创建生成器（此时函数体还没执行）")
    for i in range(3):
        v = next(g)
        print(f"  外部拿到：{v}")
    print("  再取一次会抛 StopIteration\n")


# ---------------------------------------------------------------- 3. 省内存

def demo_memory():
    print("=" * 60)
    print("3. 生成器为什么省内存")
    print("=" * 60)

    list_size = sys.getsizeof(list(range(100000)))
    gen_size = sys.getsizeof(x for x in range(100000))

    print(f"  list(range(100000)) 占用：{list_size} 字节")
    print(f"  生成器表达式占用：    {gen_size} 字节")
    print("  结论：生成器只保存'怎么算'，不保存结果，几乎不占内存\n")


# ---------------------------------------------------------------- 4. yield 做前后置（重点）

def demo_setup_teardown():
    print("=" * 60)
    print("4. 重点：yield 把函数劈成 setup 和 teardown 两半")
    print("=" * 60)

    def db_connection():
        print("    ① 连接数据库（yield 之前 = setup）")
        conn = "数据库连接对象"
        yield conn
        print("    ③ 关闭数据库连接（yield 之后 = teardown）")

    gen = db_connection()
    conn = next(gen)
    print(f"    ② 用 {conn} 查询数据")
    try:
        next(gen)               # 继续走完 yield 之后的代码
    except StopIteration:
        pass
    print("  这就是 pytest fixture 的原理\n")


# ---------------------------------------------------------------- 5. 模拟 pytest fixture

def demo_as_fixture():
    print("=" * 60)
    print("5. 把上面的写法改成 fixture 的样子（Day 3 会真的用）")
    print("=" * 60)

    def login_fixture():
        print("    [setup]   调用登录接口，拿到 token")
        token = "mock_token_abc123"
        yield token
        print("    [teardown] 调用退出接口，清理登录态")

    # 模拟 pytest 的执行方式
    gen = login_fixture()
    token = next(gen)
    print(f"    [用例]    带着 {token} 调用其他接口")
    try:
        next(gen)
    except StopIteration:
        pass
    print()


# ---------------------------------------------------------------- 6. contextmanager

@contextmanager
def file_opener(path, mode="r"):
    """用 with 语句自动管理资源"""
    print(f"    打开 {path}")
    f = open(path, mode, encoding="utf-8")
    try:
        yield f
    finally:
        print(f"    关闭 {path}")
        f.close()


def demo_contextmanager():
    print("=" * 60)
    print("6. 更优雅的写法：contextmanager + with")
    print("=" * 60)

    import tempfile
    import os
    tmp = tempfile.mktemp(suffix=".txt")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("hello")

    with file_opener(tmp) as f:
        print(f"    读到内容：{f.read()}")

    os.remove(tmp)
    print("  with 块结束时自动执行 yield 之后的代码（就算中间报错也会执行）\n")


# ---------------------------------------------------------------- 7. 大文件读取

def read_lines(path):
    """逐行产出，不一次性加载"""
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line


def demo_large_file():
    print("=" * 60)
    print("7. 实战：读大日志文件（面试常考）")
    print("=" * 60)

    import tempfile
    import os
    tmp = tempfile.mktemp(suffix=".log")
    with open(tmp, "w", encoding="utf-8") as f:
        for i in range(5):
            f.write(f"第 {i} 行：{'ERROR 出错了' if i % 2 else 'INFO 正常'}\n")

    print("  只打印含 ERROR 的行：")
    for line in read_lines(tmp):
        if "ERROR" in line:
            print(f"    {line.strip()}")

    os.remove(tmp)
    print("  要点：绝不能 f.read()，要用 for line in f\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    demo_return_vs_yield()
    demo_next()
    demo_memory()
    demo_setup_teardown()
    demo_as_fixture()
    demo_contextmanager()
    demo_large_file()

    print("=" * 60)
    print("完成。记住一句话：yield 之前是准备，yield 之后是清理")
    print("=" * 60)
