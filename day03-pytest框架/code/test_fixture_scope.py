# -*- coding: utf-8 -*-
"""
fixture 作用域演示

重点观察：不同 scope 的 fixture，打印的先后顺序不一样。

运行（一定要加 -s，否则 print 看不到）：
    pytest day03-pytest框架/code/test_fixture_scope.py -vs
"""
import pytest


# ---------------------------------------------------------------- 1. function 级（默认）

@pytest.fixture
def func_resource():
    """每条用例都会执行一次"""
    print("\n    [function] 创建")
    yield "function 级资源"
    print("    [function] 销毁")


def test_a(func_resource):
    print(f"    用例 A 使用 {func_resource}")


def test_b(func_resource):
    print(f"    用例 B 使用 {func_resource}")


# ---------------------------------------------------------------- 2. module 级

@pytest.fixture(scope="module")
def module_resource():
    """整个文件只执行一次"""
    print("\n    [module] 创建")
    yield "module 级资源"
    print("    [module] 销毁")


def test_c(module_resource):
    print(f"    用例 C 使用 {module_resource}")


def test_d(module_resource):
    print(f"    用例 D 使用 {module_resource}")


# ---------------------------------------------------------------- 3. 依赖链

@pytest.fixture(scope="module")
def db_conn(module_resource):
    """fixture 可以依赖别的 fixture"""
    print("    [db_conn] 基于 module_resource 创建连接")
    yield f"连接（依赖 {module_resource}）"
    print("    [db_conn] 关闭连接")


def test_e(db_conn):
    print(f"    用例 E 使用 {db_conn}")


# ---------------------------------------------------------------- 4. 用例失败时 teardown 还会执行吗

@pytest.fixture
def will_fail_setup():
    print("\n    [失败演示] 准备数据")
    yield "data"
    print("    [失败演示] 清理数据 ← 用例失败也能看到这行")


@pytest.mark.xfail(reason="故意失败，用来观察 teardown 是否仍然执行")
def test_fail_but_cleanup(will_fail_setup):
    print("    这条用例会断言失败")
    assert False, "故意失败"


# ---------------------------------------------------------------- 5. 类级别的 fixture

class TestWithClassScope:
    @staticmethod
    @pytest.fixture(scope="class")
    def class_resource():
        print("\n    [class] 创建")
        yield "class 级资源"
        print("    [class] 销毁")

    def test_1(self, class_resource):
        print(f"    类内用例 1 使用 {class_resource}")

    def test_2(self, class_resource):
        print(f"    类内用例 2 使用 {class_resource}")
