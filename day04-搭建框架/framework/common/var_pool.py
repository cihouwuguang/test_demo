# -*- coding: utf-8 -*-
"""
变量池：解决接口依赖

机制：
  1. 上游用例从响应里提取字段 → VarPool.set("user_id", 5)
  2. 下游用例写 ${user_id} 占位
  3. 发请求前 VarPool.replace() 换成真实值

用类变量（类属性）实现，全局唯一一份，任何地方 set 了别处都能 get 到。
这是"单例"思想的最简写法。
"""
import re


class VarPool:
    _vars = {}

    @classmethod
    def set(cls, key, value):
        """存变量"""
        cls._vars[key] = value

    @classmethod
    def get(cls, key, default=None):
        """取变量，没有返回默认值（不抛异常）"""
        return cls._vars.get(key, default)

    @classmethod
    def clear(cls):
        """清空（一般不用，除非要强隔离）"""
        cls._vars.clear()

    @classmethod
    def all(cls):
        return dict(cls._vars)

    # ------------------------------------------------------------ 替换

    @classmethod
    def replace(cls, data):
        """
        递归替换 ${xxx} 占位符

        关键设计：
          - 整串就是一个占位符（"${user_id}"）→ 保留原类型（int 还是 int）
          - 占位符只是其中一部分（"订单${id}号"）→ 只能转字符串拼接

        为什么必须区分？
          如果一律 str() 强转，int 的 userId=5 会变成 "5"，
          服务端按整数匹配用户就查不到了，这种 bug 极难排查。
        """
        if isinstance(data, str):
            full = re.fullmatch(r"\$\{(\w+)\}", data)
            if full:
                key = full.group(1)
                if key not in cls._vars:
                    raise KeyError(
                        f"变量 ${{{key}}} 不在变量池中，当前已有：{list(cls._vars.keys())}")
                return cls._vars[key]

            def _sub(m):
                key = m.group(1)
                if key not in cls._vars:
                    raise KeyError(
                        f"变量 ${{{key}}} 不在变量池中，当前已有：{list(cls._vars.keys())}")
                return str(cls._vars[key])
            return re.sub(r"\$\{(\w+)\}", _sub, data)

        if isinstance(data, dict):
            return {k: cls.replace(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.replace(i) for i in data]
        return data


if __name__ == "__main__":
    VarPool.set("user_id", 5)
    VarPool.set("token", "abc123")

    print(VarPool.replace({"userId": "${user_id}"}))           # {'userId': 5}  int
    print(VarPool.replace({"desc": "订单${user_id}号"}))        # {'desc': '订单5号'}
    print(VarPool.replace({"t": "${token}", "n": 1}))          # int 不受影响
    print(VarPool.all())
