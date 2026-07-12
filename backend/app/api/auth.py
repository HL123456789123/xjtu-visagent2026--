"""
认证相关 API 路由
- POST /api/auth/register 用户注册
- POST /api/auth/login 用户登录
- GET /api/auth/me 获取当前用户信息
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.security import get_current_user, is_super_admin
from app.core.rate_limiter import limiter
from app.database.session import get_db
from app.entity.schemas import TokenResponse, UserLogin, UserRegister, UserResponse
from app.services.user_service import user_service

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: UserRegister, db: Session = Depends(get_db)):
    """
    用户注册
    - **username**: 用户名（3-50 字符）
    - **email**: 邮箱
    - **password**: 密码（至少 6 位）
    """
    user = user_service.register(
        db=db,
        username=body.username,
        email=body.email,
        password=body.password,
    )
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: UserLogin, db: Session = Depends(get_db)):
    """
    用户登录
    - 设置 HttpOnly cookie 存储 JWT token
    - 同时返回 access_token 用于兼容
    """
    user = user_service.login(
        db=db,
        username=body.username,
        password=body.password,
    )

    access_token = user_service.create_access_token_for_user(user)
    roles = user_service.get_user_roles(db, user)
    permissions = user_service.get_user_permissions(db, user)

    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "avatar": user.avatar,
            "roles": roles,
            "permissions": permissions,
        },
    }

    response = JSONResponse(content=response_data)
    # 设置 HttpOnly cookie，防止 XSS 读取
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return response


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """获取当前登录用户信息（需要 Token 认证）"""
    roles = user_service.get_user_roles(db, current_user)
    permissions = user_service.get_user_permissions(db, current_user)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "avatar": current_user.avatar,
        "is_active": current_user.is_active,
        "is_superuser": is_super_admin(current_user, db),
        "roles": roles,
        "permissions": permissions,
        "last_login_at": current_user.last_login_at,
        "created_at": current_user.created_at,
    }


@router.post("/logout")
async def logout():
    """登出 - 清除 HttpOnly cookie"""
    response = JSONResponse(content={"message": "已登出"})
    response.delete_cookie(
        key="access_token",
        path="/",
    )
    return response
