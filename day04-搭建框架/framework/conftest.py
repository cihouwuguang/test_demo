# -*- coding: utf-8 -*-
"""
框架的 conftest.py

职责：
  1. 把框架根目录加入 sys.path（让用例能 import common / api）
  2. 注册命令行参数 --env / --strict-parallel
  3. 提供全局 fixture：client（已登录）、测试用户等

关于 -n（多进程并发）的处理，这里是最容易讲错的地方，务必看第 1 节的注释。
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

# 记录检测到的 -n 参数值，供 report_header / terminal_summary 出提示用
_N_ARGS_REMOVED = {}


def pytest_addoption(parser):
    """注册自定义命令行参数"""
    parser.addoption(
        "--env", action="store", default=None,
        help="指定运行环境，如 test / prod，默认读 config.yaml 的 default_env",
    )
    parser.addoption(
        "--strict-parallel", action="store_true", default=False,
        help="检测到 -n 时直接报错退出，而不是降级成串行（CI 上建议打开）",
    )


# ---------------------------------------------------------------- -n 的处理
#
# 【这段是整套课程里最容易被讲错的点，四份文档必须说同一件事】
#
# 事实（实测，可复现）：
#   pytest -n 2                        → 框架忽略 -n，按【串行】跑完，
#                                        **退出码 0**，78 passed
#   pytest -n 2 --strict-parallel      → 退出码 1，明确报错
#
# 也就是说，默认行为是「**带提示的降级**」，不是「直接失败」。
#
# 为什么选降级而不是直接失败？
#   学员第一次敲 -n，看到一屏 KeyError 会以为是自己把环境搞坏了。
#   框架的职责是讲清原因并让其余用例跑完，而不是卡死在报错上。
#
# 但降级有个真实风险，必须自己心里清楚（面试也常问到这里）：
#   **CI 上配了 -n 4，构建是绿的，却没人知道并发压根没生效。**
#   这比"直接失败"危险——失败至少会有人来看。
#
# 所以这里做了三件事，让"降级"不再"静默"：
#   ① 报告头提示（pytest_report_header）
#   ② 结尾再用醒目的分隔块提示一次（pytest_terminal_summary）
#   ③ 提供 --strict-parallel，让 CI 可以选择"直接失败"

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
        return (f"[提示] 检测到 -n {n}，但本框架不支持默认的多进程并发，"
                f"已忽略该参数并按【串行】执行（原因见 day04 教程第六节）")
    return None


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    结尾再提示一次 —— 只提示在开头，很容易被刷屏刷掉

    这里同时把话说明白：退出码是 0，所以 CI 上是绿的，这是必须知道的坑。
    """
    n = _N_ARGS_REMOVED.get("value")
    if not n:
        return

    terminalreporter.write_sep("=", "注意：本次并不是并发执行")
    terminalreporter.write_line(
        f"  你传了 -n {n}，但框架把它忽略了，实际按【串行】跑完，退出码 {int(exitstatus)}。")
    terminalreporter.write_line(
        "  换句话说：如果在 CI 里配 -n 4，构建会是绿的，但并发根本没生效。"
        "这是本框架的已知架构限制")
    terminalreporter.write_line(
        "  （变量池靠进程内全局变量传接口依赖，xdist 是多进程、内存不共享），"
        "不是你把环境搞坏了。")
    terminalreporter.write_line(
        "  要让它直接失败而不是降级，加参数：pytest -n 4 --strict-parallel")
    terminalreporter.write_line(
        "  想真并发，得改数据传递方式，见 day04 教程第六节。")


def pytest_configure(config):
    """
    启动前做两件事：处理不支持的用法 + 设置运行环境

    设计原则：把「用户用错了」和「框架坏了」区分开。
    不支持的用法要讲清原因，但默认不要让框架卡死在报错上——能继续跑就继续跑。
    """
    # 1 并发保护：本框架用进程内的全局变量池传递接口依赖，xdist 多进程取不到值
    n = getattr(config.option, "numprocesses", None)
    if n:
        strict = config.getoption("--strict-parallel")
        if strict:
            # CI 场景：宁可失败也不要"绿着但其实没并发"
            pytest.exit(
                f"\n检测到 -n {n} 和 --strict-parallel，而本框架不支持多进程并发。\n"
                "原因：跨用例的接口依赖放在进程内的全局变量池里，\n"
                "      xdist 是多进程、内存不共享，变量传不过去。\n"
                "处理：去掉 -n，或把依赖数据挪到外部存储 / 改造成用例自包含。\n"
                "（详细分析见 day04 教程第六节）",
                returncode=1,
            )
        # 记下来，交给 report_header / terminal_summary 去提示（这里不能自己 print）
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


# ---------------------------------------------------------------- 是否只有单元测试

def _only_unit_tests(session):
    """
    本次运行是否只收集到 unit/ 目录下的用例

    纯函数单元测试（变量池替换、JSONPath 取值、断言算子）不需要 mock 服务，
    所以这种情况跳过"服务检查"和"全局前置"，让 `pytest unit/` 能独立跑。
    """
    items = list(getattr(session, "items", []))
    if not items:
        return True

    unit_dir = os.path.normcase(os.path.abspath(os.path.join(_ROOT, "unit"))) + os.sep
    for item in items:
        path = os.path.normcase(os.path.abspath(str(getattr(item, "path", ""))))
        if not path.startswith(unit_dir):
            return False
    return True


# ---------------------------------------------------------------- 服务检查

@pytest.fixture(scope="session", autouse=True)
def check_service(request):
    """
    跑之前先确认目标服务通不通

    提示要分情况：连不上本地 mock = 忘了启动服务；
    连不上远程环境 = 正常现象（那是示例域名），不该让人去启动 mock。
    """
    if _only_unit_tests(request.session):
        return              # 单元测试不需要被测服务

    import os

    import requests
    from common.request_util import _is_local_url
    from config.config import get_config

    cfg = get_config()

    # 本机地址必须显式绕过系统代理
    #
    # 为什么：开着代理软件时，这次健康检查会被代理劫持，报出来的却是
    # 「mock 服务没启动」—— 而真相是代理问题（ProxyError 是 ConnectionError
    # 的子类，从异常信息里根本看不出来）。排查的人会去反复重启 mock 服务，
    # 重启几次都没用。健康检查自己都踩这个坑，就没资格替用例做前置判断了。
    proxies = {"http": None, "https": None} if _is_local_url(cfg.base_url) else None

    try:
        requests.get(cfg.base_url, timeout=3, proxies=proxies)
    except requests.exceptions.ProxyError as e:
        # 必须排在 RequestException 前面：代理问题的处置方式和"服务没启动"
        # 完全不同，混在一起只会让人照着错误的提示去排查。
        hint = (f"请求被系统代理拦截：{e}\n\n"
                f"环境里的代理配置：HTTP_PROXY={os.environ.get('HTTP_PROXY')}，"
                f"HTTPS_PROXY={os.environ.get('HTTPS_PROXY')}\n\n"
                "本机服务请在环境变量里设置：\n"
                "    NO_PROXY=127.0.0.1,localhost\n"
                "或者临时关掉代理软件再跑。\n")
        pytest.exit("\n" + "=" * 62 + "\n" + hint + "=" * 62, returncode=1)
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
def prepare(client, request):
    """
    测试前置准备（autouse：所有用例自动执行）

    做两件事：
      1. 登录，把 token 设进 client 的全局请求头
      2. 创建一个测试用户，把 id 存进变量池供用例用 ${test_user_id}
    """
    if _only_unit_tests(request.session):
        yield
        return              # 单元测试不做全局前置

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

    # 兜底清理：YAML 里「删除刚创建的用户」那条用例自己会删，
    # 但它一旦失败、或者被 -k 过滤掉没跑到，就会留下脏数据。
    # 清理动作不该依赖"前置用例恰好成功"——所以这里再兜一层。
    created = VarPool.get("created_user_id")
    if created and created != user_id:
        client.delete(f"/api/user/{created}")
        log.info(f"【全局后置】兜底清理 YAML 用例创建的用户：{created}")
