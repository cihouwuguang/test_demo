# -*- coding: utf-8 -*-
"""
课程配套的练习接口服务（Flask）

启动：
    python mock_server/app.py
    或指定端口：python mock_server/app.py 5001

启动后访问 http://127.0.0.1:5000 可以看到接口清单。
数据存在内存里，重启服务会重置。
"""

import sys
import time
import hashlib

from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------- 模拟数据

# 用户表（内存字典）
USERS = {
    1: {"id": 1, "username": "admin", "phone": "13800000000", "role": "admin"},
    2: {"id": 2, "username": "tester", "phone": "13900000000", "role": "user"},
}
_next_user_id = 3

# 订单表
ORDERS = {}
_next_order_id = 1001

# 合法的 token（登录后返回，也可以用这个固定的做调试）
VALID_TOKEN = "mock_token_abc123"

# 用于签名的密钥
SIGN_KEY = "demo_secret_key"


# ---------------------------------------------------------------- 工具函数

def ok(data=None, msg="success"):
    """统一成功响应"""
    return jsonify({"code": 0, "msg": msg, "data": data}), 200


def fail(code, msg, http_status=200):
    """统一失败响应"""
    return jsonify({"code": code, "msg": msg, "data": None}), http_status


def check_token():
    """从请求头取 token 并校验"""
    token = request.headers.get("token") or request.headers.get("Authorization")
    if token and token.startswith("Bearer "):
        token = token[7:]
    if token != VALID_TOKEN:
        return False
    return True


# ---------------------------------------------------------------- 首页

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "AA 课程练习接口",
        "endpoints": {
            "POST /api/login": "登录，返回 token",
            "GET  /api/user/<id>": "查用户（需 token）",
            "POST /api/user": "新增用户（需 token）",
            "PUT  /api/user/<id>": "更新用户（需 token）",
            "DELETE /api/user/<id>": "删除用户（需 token）",
            "GET  /api/users": "用户列表（需 token，支持 page/size）",
            "POST /api/order": "创建订单（需 token，依赖用户 id）",
            "GET  /api/order/<id>": "查订单（需 token）",
            "POST /api/sign/verify": "验签接口演示",
            "GET  /api/slow": "慢接口，3 秒后返回（演示 timeout）",
            "GET  /api/error": "故意报错（演示异常处理）",
        },
        "default_token": VALID_TOKEN,
    })


# ---------------------------------------------------------------- 登录

@app.route("/api/login", methods=["POST"])
def login():
    """
    登录接口
    请求体 JSON：{"username": "admin", "password": "123456"}
    """
    body = request.get_json(silent=True) or {}
    username = body.get("username")
    password = body.get("password")

    # 参数校验
    if not username or not password:
        return fail(1001, "用户名或密码不能为空")
    if len(username) < 2 or len(username) > 20:
        return fail(1002, "用户名长度必须在 2-20 之间")

    # 账号密码校验
    if username == "admin" and password == "123456":
        # 真实场景这里是对密码做哈希后再比对，这里简化处理
        return ok({"token": VALID_TOKEN, "userId": 1, "username": "admin"})

    return fail(1003, "用户名或密码错误")


# ---------------------------------------------------------------- 用户

@app.route("/api/user/<int:uid>", methods=["GET"])
def get_user(uid):
    if not check_token():
        return fail(401, "未授权，请先登录", 401)
    user = USERS.get(uid)
    if not user:
        return fail(2001, "用户不存在")
    return ok(user)


@app.route("/api/user", methods=["POST"])
def create_user():
    global _next_user_id
    if not check_token():
        return fail(401, "未授权，请先登录", 401)

    body = request.get_json(silent=True) or {}
    username = body.get("username")
    phone = body.get("phone")

    if not username:
        return fail(2002, "username 不能为空")
    if not phone or len(phone) != 11:
        return fail(2003, "手机号必须是 11 位")

    uid = _next_user_id
    _next_user_id += 1
    USERS[uid] = {"id": uid, "username": username, "phone": phone, "role": "user"}
    return ok({"id": uid, "username": username, "phone": phone})


@app.route("/api/user/<int:uid>", methods=["PUT"])
def update_user(uid):
    if not check_token():
        return fail(401, "未授权，请先登录", 401)
    if uid not in USERS:
        return fail(2001, "用户不存在")

    body = request.get_json(silent=True) or {}
    if "username" in body:
        USERS[uid]["username"] = body["username"]
    if "phone" in body:
        USERS[uid]["phone"] = body["phone"]
    return ok(USERS[uid])


@app.route("/api/user/<int:uid>", methods=["DELETE"])
def delete_user(uid):
    if not check_token():
        return fail(401, "未授权，请先登录", 401)
    if uid not in USERS:
        return fail(2001, "用户不存在")
    USERS.pop(uid)
    return ok({"id": uid})


@app.route("/api/users", methods=["GET"])
def list_users():
    if not check_token():
        return fail(401, "未授权，请先登录", 401)

    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    all_users = list(USERS.values())
    start = (page - 1) * size
    return ok({
        "total": len(all_users),
        "page": page,
        "size": size,
        "list": all_users[start:start + size],
    })


# ---------------------------------------------------------------- 订单（体现接口依赖）

@app.route("/api/order", methods=["POST"])
def create_order():
    """创建订单：必须先有用户，体现接口依赖"""
    global _next_order_id
    if not check_token():
        return fail(401, "未授权，请先登录", 401)

    body = request.get_json(silent=True) or {}
    user_id = body.get("userId")
    amount = body.get("amount")
    goods = body.get("goodsName", "默认商品")

    if user_id not in USERS:
        return fail(3001, "下单用户不存在")
    if not isinstance(amount, (int, float)) or amount <= 0:
        return fail(3002, "金额必须大于 0")

    oid = _next_order_id
    _next_order_id += 1
    ORDERS[oid] = {
        "orderId": oid,
        "userId": user_id,
        "goodsName": goods,
        "amount": amount,
        "status": "CREATED",
    }
    return ok(ORDERS[oid])


@app.route("/api/order/<int:oid>", methods=["GET"])
def get_order(oid):
    if not check_token():
        return fail(401, "未授权，请先登录", 401)
    order = ORDERS.get(oid)
    if not order:
        return fail(3003, "订单不存在")
    return ok(order)


@app.route("/api/order/<int:oid>/pay", methods=["POST"])
def pay_order(oid):
    """支付订单：演示状态流转"""
    if not check_token():
        return fail(401, "未授权，请先登录", 401)
    order = ORDERS.get(oid)
    if not order:
        return fail(3003, "订单不存在")
    if order["status"] == "PAID":
        return fail(3004, "订单已支付，请勿重复提交")
    order["status"] = "PAID"
    return ok(order)


# ---------------------------------------------------------------- 特殊场景

@app.route("/api/sign/verify", methods=["POST"])
def sign_verify():
    """
    验签演示
    签名规则：sign = md5(key + 参数按 key 升序拼接 + timestamp)
    请求头带：sign、timestamp
    """
    sign = request.headers.get("sign")
    timestamp = request.headers.get("timestamp")

    if not sign or not timestamp:
        return fail(4001, "缺少 sign 或 timestamp")
    if abs(time.time() - int(timestamp)) > 300:
        return fail(4002, "请求已过期")

    body = request.get_json(silent=True) or {}
    raw = "".join(f"{k}{body[k]}" for k in sorted(body.keys()))
    expect = hashlib.md5((SIGN_KEY + raw + timestamp).encode()).hexdigest()

    if sign != expect:
        return fail(4003, f"签名错误，期望 {expect}")
    return ok({"msg": "验签通过"})


@app.route("/api/slow", methods=["GET"])
def slow():
    """故意慢 3 秒，用来演示 timeout"""
    time.sleep(3)
    return ok({"msg": "终于返回了"})


@app.route("/api/error", methods=["GET"])
def error():
    """故意抛异常，用来演示异常处理"""
    raise RuntimeError("这里是故意抛出的异常，用来测试客户端的容错")


# ---------------------------------------------------------------- 启动

if __name__ == "__main__":
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    print(f"mock 服务启动中... 访问 http://127.0.0.1:{port}")
    # debug=False 的原因：
    #   debug=True 时 Flask 会开启 reloader，额外 fork 一个进程，
    #   结果是「同一个请求被打两次」「启动日志打印两遍」，
    #   初学者很容易以为代码有问题。练习用不到热重载，关掉更省心。
    app.run(host="127.0.0.1", port=port, debug=False)
