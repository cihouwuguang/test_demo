# -*- coding: utf-8 -*-
"""
订单模块接口
"""
from api.base_api import BaseAPI


class OrderAPI(BaseAPI):
    """订单模块"""

    def create_order(self, user_id, amount, goods_name="自动化测试商品"):
        """创建订单"""
        return self.client.post("/api/order", json={
            "userId": user_id,
            "amount": amount,
            "goodsName": goods_name,
        })

    def get_order(self, order_id):
        """查询订单"""
        return self.client.get(f"/api/order/{order_id}")

    def pay_order(self, order_id):
        """支付订单"""
        return self.client.post(f"/api/order/{order_id}/pay")
