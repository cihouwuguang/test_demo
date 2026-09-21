# -*- coding: utf-8 -*-
"""
yield 与生成器：pytest 前后置的原理就在这

运行：python day01-Python核心/code/02_yield.py
"""
import os
import tempfile
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

    # 注意两种量法的区别（这是个容易被问倒的点）：
    #   sys.getsizeof 只算「这个对象本身」占多少字节，不算它引用的元素。
    #   所以 sys.getsizeof(list) 得到的只是「容器外壳」，会把内存差距严重低估。
    #   要量「真实峰值内存」得用 tracemalloc。
    import sys
    import tracemalloc

    n = 1_000_000

    tracemalloc.start()
    lst = [x for x in range(n)]
    list_peak = tracemalloc.get_traced_memory()[1]      # 峰值 = 38 MB 左右
    del lst
    tracemalloc.stop()

    gen = (x for x in range(n))          # 生成器对象本身（还没开始算）

    print(f"  列表 [x for x in range({n})]：")
    print(f"      tracemalloc 实测峰值占用：{list_peak / 1024 / 1024:.1f} MB")
    print(f"      sys.getsizeof 只报：{sys.getsizeof([x for x in range(n)])} 字节"
          f" ← 只算了容器外壳，没算元素")
    print(f"  生成器 (x for x in range({n})) 对象本身：{sys.getsizeof(gen)} 字节")
    print("  结论：列表把 100 万个结果全存在内存里；")
    print("        生成器只保存「怎么算」和当前进度，几乎不占内存\n")


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
def file_opener_safe(path, mode="r"):
    """
    推荐写法：yield 包在 try/finally 里

    @contextmanager 的异常路径必须讲清楚：
      with 体里抛异常时，contextlib 会把异常 throw 回 yield 那一行。
      - 生成器没捕获 → 异常从 yield 处抛出，yield 之后的代码【不会执行】
      - 包了 try/finally → finally 一定会跑，资源不会泄漏
    """
    print(f"    [safe] 打开 {path}")
    f = open(path, mode, encoding="utf-8")
    try:
        yield f
    finally:
        print(f"    [safe] 关闭 {path}")
        f.close()


@contextmanager
def file_opener_naive(path, mode="r"):
    """
    反面写法：yield 之后直接写清理代码（没有 try/finally）

    正常结束时看起来没问题，一旦 with 体里出异常，清理代码就被跳过了。
    新手最容易这么写，因为平时测不出来。
    """
    print(f"    [naive] 打开 {path}")
    f = open(path, mode, encoding="utf-8")
    yield f
    print(f"    [naive] 关闭 {path}")      # ← 出异常时这行执行不到
    f.close()


def demo_contextmanager():
    print("=" * 60)
    print("6. 更优雅的写法：contextmanager + with")
    print("=" * 60)

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                     encoding="utf-8") as tmp_f:
        tmp = tmp_f.name
        tmp_f.write("hello")

    # 6.1 正常路径：两种写法都能清理
    print("  【正常结束】")
    with file_opener_safe(tmp) as f:
        print(f"      读到内容：{f.read()}")

    # 6.2 异常路径：这才是区别所在
    print("\n  【with 体里抛异常 —— 关键对比】")
    print("    naive 版（yield 后直接写清理）：")
    try:
        with file_opener_naive(tmp) as f:
            raise RuntimeError("模拟用例中途失败")
    except RuntimeError:
        pass
    print("      → 上面没有出现「[naive] 关闭」，清理被跳过了")

    print("    safe 版（try/finally）：")
    try:
        with file_opener_safe(tmp) as f:
            raise RuntimeError("模拟用例中途失败")
    except RuntimeError:
        pass
    print("      → 上面出现了「[safe] 关闭」，finally 保证清理执行")

    os.remove(tmp)
    print("\n  结论：@contextmanager 只有包了 try/finally，")
    print("        『出异常也清理』才成立；否则异常会把 yield 之后的代码跳过。\n")


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

    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False,
                                     encoding="utf-8") as f:
        tmp = f.name
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
