"""
安全工具模块
- 密码哈希与校验（bcrypt）
- JWT Token 生成与验证
- 用户认证依赖
- RBAC 权限校验依赖
"""

from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import bcrypt
from app.config.settings import settings


def hash_password(password: str) -> str:
    """将明文密码加密为哈希值"""
    max_length = 72
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > max_length:
        password_bytes = password_bytes[:max_length]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与哈希值是否匹配"""
    max_length = 72
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > max_length:
        password_bytes = password_bytes[:max_length]
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    """
    生成 JWT Access Token

    Args:
        data: Token 载荷数据，通常包含 {"sub": user_id}

    Returns:
        JWT Token 字符串
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    解析 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        Token 载荷数据

    Raises:
        JWTError: Token 无效或已过期
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# OAuth2 密码模式，用于从请求 Header 中提取 Token
# 设置 auto_error=False，当没有 Authorization header 时不抛出异常，而是返回 None
# 这样可以继续从 cookie 中读取 token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db=None,
):
    """
    从 JWT Token 中解析当前用户
    支持从 Authorization header 或 HttpOnly cookie 中读取 token
    在需要认证的路由中通过 Depends(get_current_user) 使用
    """
    from app.database.session import get_db as _get_db
    from app.services.user_service import user_service

    # 优先从 Authorization header 读取，其次从 cookie 读取
    if not token:
        token = request.cookies.get("access_token")

    _own_db = False
    if db is None:
        db_gen = _get_db()
        db = next(db_gen)
        _own_db = True

    try:
        credentials_exception = HTTPException(
            status_code=401,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
        if not token:
            raise credentials_exception
        try:
            payload = decode_access_token(token)
            user_id_str: str = payload.get("sub")
            if user_id_str is None:
                raise credentials_exception
            user_id = int(user_id_str)
        except (JWTError, ValueError):
            raise credentials_exception

        user = user_service.get_user_by_id(db, user_id)
        if user is None:
            raise credentials_exception
        return user
    finally:
        if _own_db:
            db.close()


# ── RBAC 权限校验依赖 ──────────────────────────────────


class RequirePermission:
    """
    权限校验依赖工厂

    用法：
        @router.delete("/models/{id}", dependencies=[Depends(RequirePermission("model:delete"))])

    校验逻辑：
        1. 超级管理员（is_superuser=True）直接放行
        2. 查询用户关联角色拥有的权限编码，匹配则放行
    """

    def __init__(self, permission_code: str):
        self.permission_code = permission_code

    async def __call__(
        self,
        current_user=Depends(get_current_user),
        db: Session = Depends(),
    ):
        from app.database.session import get_db as _get_db

        # 超级管理员直接放行
        if current_user.is_superuser:
            return current_user

        # 查询用户是否拥有指定权限
        from app.entity.db_models import UserRole, RolePermission, Permission

        _own_db = False
        if db is None:
            db_gen = _get_db()
            db = next(db_gen)
            _own_db = True

        try:
            has_permission = (
                db.query(Permission)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .join(UserRole, UserRole.role_id == RolePermission.role_id)
                .filter(
                    UserRole.user_id == current_user.id,
                    Permission.code == self.permission_code,
                )
                .first()
            )

            if not has_permission:
                raise HTTPException(
                    status_code=403,
                    detail=f"权限不足，需要权限: {self.permission_code}",
                )

            return current_user
        finally:
            if _own_db:
                db.close()


class RequireSuperuser:
    """
    超级管理员校验依赖

    用法：
        @router.get("/admin/xxx", dependencies=[Depends(RequireSuperuser())])
    """

    async def __call__(self, current_user=Depends(get_current_user)):
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="权限不足，需要管理员权限",
            )
        return current_user
