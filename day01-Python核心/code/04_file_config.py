# -*- coding: utf-8 -*-
"""
文件读写：JSON 与 YAML —— 数据驱动的基础

用例数据不能写死在代码里，要放到文件里。这是 Day 4 数据驱动的前置技能。

运行：python day01-Python核心/code/04_file_config.py
"""
import json
import os
import tempfile

try:
    import yaml
except ImportError:
    yaml = None
    print("提示：PyYAML 没装，执行 pip install PyYAML 后 YAML 部分才能运行")


# ---------------------------------------------------------------- JSON

def demo_json():
    print("=" * 60)
    print("1. JSON 读写")
    print("=" * 60)

    tmp = os.path.join(tempfile.gettempdir(), "aa_demo_user.json")

    data = {"username": "admin", "password": "123456", "desc": "中文不会被转义"}

    # 写：ensure_ascii=False 保证中文正常，indent=2 让格式好看
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("  写入完成，文件内容：")
    with open(tmp, encoding="utf-8") as f:
        print("    " + f.read().replace("\n", "\n    "))

    # 读
    with open(tmp, encoding="utf-8") as f:
        loaded = json.load(f)
    print(f"  读出来：{loaded}")

    os.remove(tmp)
    print("\n  要点：")
    print("    - ensure_ascii=False 不加的话中文会变成 \\u4e2d\\u6587")
    print("    - with open(...) 用完自动关文件，不用 f.close()\n")


# ---------------------------------------------------------------- YAML

CASE_YAML = """
# 一条用例的数据
name: 登录成功
request:
  method: POST
  url: /api/login
  json:
    username: admin
    password: "123456"
validate:
  - eq: [$.code, 0]
  - eq: [$.data.username, admin]
"""

CONFIG_YAML = """
# 环境配置
test:
  base_url: http://127.0.0.1:5000
  timeout: 5
prod:
  base_url: https://api.example.com
  timeout: 10
"""


def demo_yaml():
    if yaml is None:
        return
    print("=" * 60)
    print("2. YAML 读写（自动化框架更常用，因为能写注释）")
    print("=" * 60)

    case = yaml.safe_load(CASE_YAML)
    print(f"  用例名：{case['name']}")
    print(f"  请求方法：{case['request']['method']}")
    print(f"  请求体：{case['request']['json']}")
    print(f"  断言：{case['validate']}")

    config = yaml.safe_load(CONFIG_YAML)
    print(f"\n  测试环境地址：{config['test']['base_url']}")
    print(f"  生产环境地址：{config['prod']['base_url']}")
    print("  切换环境只要换一个 key，这就是配置管理的雏形\n")

    print("  YAML 三个必须记住的规则：")
    print("    1. 缩进只能用空格，不能用 Tab")
    print("    2. 冒号后面必须有空格")
    print("    3. 密码之类的纯数字要加引号，否则会被解析成数字\n")


# ---------------------------------------------------------------- 实战

def demo_practical():
    print("=" * 60)
    print("3. 实战：读 YAML 用例，遍历执行（Day 4 会真的发请求）")
    print("=" * 60)

    if yaml is None:
        print("  （跳过：PyYAML 未安装）\n")
        return

    cases_yaml = """
- name: 登录成功
  username: admin
  password: "123456"
  expect_code: 0
- name: 密码错误
  username: admin
  password: wrong
  expect_code: 1003
- name: 用户名为空
  username: ""
  password: "123456"
  expect_code: 1001
"""
    cases = yaml.safe_load(cases_yaml)
    for i, case in enumerate(cases, 1):
        print(f"  用例{i}：{case['name']}")
        print(f"          入参 {case['username']} / {case['password']}，期望 code={case['expect_code']}")
    print("\n  三条用例只写了一份执行逻辑，数据从文件来 —— 这就是数据驱动\n")


# ---------------------------------------------------------------- 主程序

if __name__ == "__main__":
    demo_json()
    demo_yaml()
    demo_practical()

    print("=" * 60)
    print("完成。记住：用例数据放文件，执行逻辑放代码")
    print("=" * 60)
