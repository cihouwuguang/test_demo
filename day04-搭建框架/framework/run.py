# -*- coding: utf-8 -*-
"""
框架入口：一条命令跑全部

用法：
    python run.py                      # 跑全部，出 HTML 报告
    python run.py -m smoke             # 只跑冒烟
    python run.py --env=prod           # 指定环境
    python run.py testcases/test_login.py   # 只跑某个文件

说明：
    这里用 pytest.main() 调用，等价于在命令行敲 pytest，
    好处是可以预置默认参数（比如报告路径），用户不用记长命令。
"""
import os
import sys

import pytest

# 保证 import common / api 时能找到（直接运行 run.py 时 sys.path[0] 就是本目录）
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 报告目录
REPORT_DIR = os.path.join(_ROOT, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)
REPORT_FILE = os.path.join(REPORT_DIR, "report.html")


def main():
    # 默认参数：详细输出 + HTML 报告（自包含，单文件可直接打开）
    default_args = [
        "--html=" + REPORT_FILE,
        "--self-contained-html",
    ]

    # 用户命令行传的参数追加在后面（优先级更高）
    user_args = sys.argv[1:]

    print("=" * 60)
    print("开始执行自动化测试")
    print(f"报告将生成到：{REPORT_FILE}")
    print("=" * 60)

    exit_code = pytest.main(default_args + user_args)

    print("=" * 60)
    if exit_code == 0:
        print("全部通过")
    else:
        print(f"存在失败用例，退出码 {exit_code}")
    print(f"报告位置：{REPORT_FILE}")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
