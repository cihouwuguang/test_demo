# -*- coding: utf-8 -*-
"""
框架的 conftest.py

职责：
  1. 把框架根目录加入 sys.path（让用例能 import common / api）
  2. 注册命令行参数 --env
  3. 提供全局 fixture：client（已登录）、测试用户等
"""
import os
import sys

import pytest

# 把 framework 目录加入模块搜索路径
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from common.logger import get_logger                       # noqa: E402
from common.request_util import get_client, reset_client   # noqa: E402
from common.var_pool import VarPool                        # noqa: E402

log = get_logger()


# ---------------------------------------------------------------- 命令行参数

# 记录检测到的 -n 参数值，供 pytest_report_header 出提示用
_N_ARGS_REMOVED = {}


def pytest_addoption(parser):
    """注册自定义命令行参数：pytest --env=prod"""
    parser.addoption(
        "--env", action="store", default=None,
        help="指定运行环境，如 test / prod，默认读 config.yaml 的 default_env",
    )


def pytest_report_header(config):
    """
    把「-n 被忽略」这件事显示在开头的信息头里

    为什么不直接在 pytest_configure 里 print：
      那个阶段 pytest 的 capture 已经介入，往 stdout / stderr 写长文本会被反复
      回显——实测同一段提示被输出了 62 遍，一屏全是重复的，反而看不清重点。
      交给 pytest 官方这个钩子，由 pytest 自己打印，天然只出现一次。
      完整原因写在 day04 教程第六节，这里只放一句提醒。
    """
    n = _N_ARGS_REMOVED.get("value")
    if n:
        return (f"[提示] 检测到 -n {n}，但本框架暂不支持多进程并发，"
                f"已忽略该参数并按串行执行（原因见 day04 教程第六节）")
    return None


def pytest_configure(config):
    """
    启动前做两件事：处理不支持的用法 + 设置运行环境

    设计原则：把「用户用错了」和「框架坏了」区分开。
    不支持的用法要讲清原因，但不要让框架卡死在报错上——能继续跑就继续跑。
    """
    # 1 并发保护：本框架用进程内的全局变量池传递接口依赖，xdist 多进程取不到值
    n = getattr(config.option, "numprocesses", None)
    if n:
        # 记下来，交给 pytest_report_header 去提示（这里不能自己 print，原因见下）
        _N_ARGS_REMOVED["value"] = n
        # 把并发关掉：用例照常串行跑完，而不是一条都跑不了
        config.option.numprocesses = None
        config.option.dist = "no"

    # 2 环境校验：环境名写错时给明确提示，而不是所有用例一起 ERROR
    env = config.getoption("--env")
    if env:
        from config.config import set_env, get_config
        set_env(env)
        try:
            get_config()
        except KeyError as e:
            # 注意用 e.args[0]：KeyError 的 str() 会额外包一层引号，直接拼会显示成
            # 环境名无效："配置里没有环境 xxx"，很怪
            pytest.exit(
                f"\n环境名无效：{e.args[0]}\n"
                "请检查 config.yaml 里的环境名，或去掉 --env 直接用默认环境。",
                returncode=1,
            )
        log.info(f"命令行指定环境：{env}")


# ---------------------------------------------------------------- 服务检查

@pytest.fixture(scope="session", autouse=True)
def check_service():
    """
    跑之前先确认目标服务通不通

    提示要分情况：连不上本地 mock = 忘了启动服务；
    连不上远程环境 = 正常现象（那是示例域名），不该让人去启动 mock。
    """
    import requests
    from config.config import get_config

    cfg = get_config()
    try:
        requests.get(cfg.base_url, timeout=3)
    except requests.exceptions.RequestException:
        if "127.0.0.1" in cfg.base_url or "localhost" in cfg.base_url:
            hint = (f"连不上本地服务：{cfg.base_url}\n\n"
                    "mock 服务没启动。请另开一个终端执行：\n"
                    "    python mock_server\\app.py\n")
        else:
            hint = (f"连不上目标环境：{cfg.base_url}（当前环境 {cfg.env_name}）\n\n"
                    "这不是本地 mock 服务，连不上通常是正常的。\n"
                    "如果你只是想跑练习用例，去掉 --env 就会回到默认环境：\n"
                    "    python run.py\n")
        pytest.exit("\n" + "=" * 62 + "\n" + hint + "=" * 62, returncode=1)


# ---------------------------------------------------------------- 核心 fixture

@pytest.fixture(scope="session")
def client():
    """
    全局唯一的请求客户端

    session 级：整个测试过程只创建一次，登录状态共享
    用 yield 保证最后关闭连接（Day 1 的知识点）

    注意这里走 get_client() 单例，而不是 RequestClient() 新建：
    这样业务类里如果忘了传 client，拿到的也是同一个已登录对象，
    不会出现「fixture 这份登录了、单例那份没登录」的两份实例。
    """
    c = get_client()
    yield c
    reset_client()


@pytest.fixture(scope="session", autouse=True)
def prepare(client):
    """
    测试前置准备（autouse：所有用例自动执行）

    做两件事：
      1. 登录，把 token 设进 client 的全局请求头
      2. 创建一个测试用户，把 id 存进变量池供用例用 ${test_user_id}
    """
    log.info("=" * 50)
    log.info("【全局前置】开始准备测试数据")

    # 1 登录
    resp = client.post("/api/login",
                       json={"username": "admin", "password": "123456"})
    assert resp.status_code == 200, "登录接口没通"
    token = resp.json()["data"]["token"]
    client.set_header("token", token)
    VarPool.set("token", token)
    log.info("【全局前置】登录完成，token 已设置到全局请求头")

    # 2 创建测试用户
    resp = client.post("/api/user", json={
        "username": "framework_test_user",
        "phone": "13600001111",
    })
    assert resp.json()["code"] == 0, f"创建测试用户失败：{resp.text}"
    user_id = resp.json()["data"]["id"]
    VarPool.set("test_user_id", user_id)
    log.info(f"【全局前置】测试用户已创建：{user_id}")

    yield

    # 3 清理（所有用例跑完后）
    client.delete(f"/api/user/{user_id}")
    log.info("【全局后置】测试数据已清理")
