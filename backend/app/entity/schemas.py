"""
Pydantic 请求/响应模型
用于 API 接口的数据验证和序列化
分层原则：
- Create 模型：创建资源时的请求体
- Update 模型：更新资源时的请求体（所有字段可选）
- Response 模型：API 返回的响应体（过滤敏感字段）
- List 模型：分页列表查询的参数和响应
"""

from datetime import datetime
from typing import Optional, Union
from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════
# 一、用户与权限
# ══════════════════════════════════════════════════════════════

# --- 认证相关 ---


class UserRegister(BaseModel):
    """用户注册请求"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")


class UserLogin(BaseModel):
    """用户登录请求"""

    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class UserBrief(BaseModel):
    """用户简要信息（嵌入在 Token 响应中）"""

    id: int
    username: str
    email: str
    avatar: Optional[str] = None
    roles: list[str] = []

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """登录成功响应"""

    access_token: str
    token_type: str = "bearer"
    user: UserBrief


# --- 用户管理 ---


class UserResponse(BaseModel):
    """用户详情响应"""

    id: int
    username: str
    email: str
    phone: Optional[str] = None
    avatar: Optional[str] = None
    is_active: bool
    is_superuser: bool
    roles: list[str] = []
    last_login_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    """用户信息更新"""

    phone: Optional[str] = None
    avatar: Optional[str] = None
    email: Optional[str] = None


class ChangePassword(BaseModel):
    """修改密码"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# --- 角色权限 ---


class RoleResponse(BaseModel):
    """角色响应"""

    id: int
    name: str
    display_name: str
    description: Optional[str] = None
    is_system: bool
    permissions: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleCreate(BaseModel):
    """创建角色"""

    name: str = Field(..., min_length=2, max_length=50, description="角色标识")
    display_name: str = Field(..., description="角色显示名")
    description: Optional[str] = None
    permission_codes: list[str] = Field(default=[], description="权限编码列表")


class PermissionResponse(BaseModel):
    """权限响应"""

    id: int
    code: str
    name: str
    module: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# 六、通用模型
# ══════════════════════════════════════════════════════════════


class ApiResponse(BaseModel):
    """统一 API 响应"""

    code: int = 200
    message: str = "success"
    data: Optional[Union[dict, list]] = None


class PageParams(BaseModel):
    """分页查询参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PageResponse(BaseModel):
    """分页响应"""

    total: int
    page: int
    page_size: int
    total_pages: int
    items: list


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = "healthy"
    app_name: str
    version: str
    database: Optional[str] = None
    redis: Optional[str] = None
    minio: Optional[str] = None
