# -*- coding: utf-8 -*-
"""
用户模块接口

只写路径和业务参数，公共能力继承自 BaseAPI
"""
from api.base_api import BaseAPI


class UserAPI(BaseAPI):
    """用户模块"""

    def login(self, username, password):
        """登录"""
        return self.client.post("/api/login",
                                json={"username": username, "password": password})

    def get_user(self, uid):
        """查询用户（需要 token）"""
        return self.client.get(f"/api/user/{uid}")

    def list_users(self, page=1, size=10):
        """用户列表"""
        return self.client.get("/api/users", params={"page": page, "size": size})

    def create_user(self, username, phone):
        """创建用户"""
        return self.client.post("/api/user",
                                json={"username": username, "phone": phone})

    def update_user(self, uid, **kwargs):
        """更新用户"""
        return self.client.put(f"/api/user/{uid}", json=kwargs)

    def delete_user(self, uid):
        """删除用户"""
        return self.client.delete(f"/api/user/{uid}")
