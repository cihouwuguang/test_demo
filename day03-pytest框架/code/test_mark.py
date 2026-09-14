# -*- coding: utf-8 -*-
"""
标记 mark：跳过、预期失败、分组执行

常用命令：
    pytest -m smoke          # 只跑冒烟用例
    pytest -m "not slow"     # 不跑慢用例
    pytest -m "bug"          # 只看已知问题

运行：pytest day03-pytest框架/code/test_mark.py -vs
"""
import sys

import pytest

from conftest import BASE_URL


# ---------------------------------------------------------------- 1. 冒烟

@pytest.mark.smoke
def test_login_smoke(api):
    """冒烟用例：最核心的流程，提交代码时必跑"""
    r = api.post(f"{BASE_URL}/api/login",
                 json={"username": "admin", "password": "123456"})
    assert r.json()["code"] == 0


@pytest.mark.smoke
def test_query_user_smoke(api):
    r = api.get(f"{BASE_URL}/api/user/1")
    assert r.json()["code"] == 0


# ---------------------------------------------------------------- 2. 慢用例

@pytest.mark.slow
def test_slow_api(api):
    """慢用例：放晚上跑，别占用提交时的时间"""
    r = api.get(f"{BASE_URL}/api/slow")     # 这个接口要 3 秒
    assert r.json()["code"] == 0


# ---------------------------------------------------------------- 3. 无条件跳过

@pytest.mark.skip(reason="这个功能还没开发完，等下个版本")
def test_not_implemented():
    assert False      # 不会执行


# ---------------------------------------------------------------- 4. 条件跳过

@pytest.mark.skipif(sys.platform == "win32", reason="这个用例只在 Linux 上跑")
def test_linux_only():
    assert True


@pytest.mark.skipif(sys.version_info < (3, 9), reason="需要 Python 3.9+")
def test_python39_feature():
    assert True


# ---------------------------------------------------------------- 5. 预期失败

@pytest.mark.bug
@pytest.mark.xfail(reason="已知 bug：不存在的用户应该返回 404，现在返回了 200")
def test_known_bug(api):
    """
    标记为 xfail 后，失败不算失败，不影响整体结果

    比注释掉或直接删掉要好 —— 问题还在视野里
    """
    r = api.get(f"{BASE_URL}/api/user/99999")
    assert r.status_code == 404, f"期望 404，实际 {r.status_code}"


@pytest.mark.xfail(reason="这条实际上会通过，演示 xpass", strict=False)
def test_maybe_pass():
    """xfail 的用例如果通过了，会显示 xpassed"""
    assert True


# ---------------------------------------------------------------- 6. 组合标记

@pytest.mark.smoke
@pytest.mark.slow
def test_multi_marks(api):
    """一条用例可以有多个标记"""
    r = api.get(f"{BASE_URL}/api/users", params={"page": 1, "size": 5})
    assert r.json()["code"] == 0
