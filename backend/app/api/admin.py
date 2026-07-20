"""Fixed-role administrator API for user lifecycle management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import RequireAdmin
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.schemas import (
    AdminPasswordReset,
    ApiResponse,
    UserAdminUpdate,
    UserProductRoleUpdate,
    UserStatusUpdate,
)
from app.services.user_service import user_service

router = APIRouter(prefix="/api/admin", tags=["用户管理"])


@router.get("/users", response_model=ApiResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    del current_user
    result = user_service.get_user_list(
        db=db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_active=is_active,
    )
    return ApiResponse(code=200, data=result)


@router.get("/users/{user_id}", response_model=ApiResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    del current_user
    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return ApiResponse(
        code=200,
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar": user.avatar,
            "is_active": user.is_active,
            "role": user_service.get_product_role(db, user),
            "roles": [user_service.get_product_role(db, user)],
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        },
    )


@router.put("/users/{user_id}", response_model=ApiResponse)
async def update_user(
    user_id: int,
    data: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    kwargs = data.model_dump(exclude_unset=True)
    if not kwargs:
        raise HTTPException(status_code=400, detail="未提供任何更新字段")
    user_service.admin_update_user(db, user_id, current_user, **kwargs)
    return ApiResponse(code=200, message="用户信息更新成功")


@router.put("/users/{user_id}/role", response_model=ApiResponse)
async def set_user_role(
    user_id: int,
    data: UserProductRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    user = user_service.set_user_role(db, user_id, data.role, current_user)
    return ApiResponse(
        code=200,
        message="用户角色更新成功",
        data={"user_id": user.id, "role": data.role},
    )


@router.put("/users/{user_id}/status", response_model=ApiResponse)
async def toggle_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    user_service.toggle_user_active(db, user_id, data.is_active, current_user)
    return ApiResponse(code=200, message="用户已启用" if data.is_active else "用户已禁用")


@router.post("/users/{user_id}/reset-password", response_model=ApiResponse)
async def reset_user_password(
    user_id: int,
    data: AdminPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    user_service.reset_password(db, user_id, data.new_password, current_user)
    return ApiResponse(code=200, message="用户密码已重置")


@router.delete("/users/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequireAdmin()),
):
    user_service.delete_user(db, user_id, current_user)
    return ApiResponse(code=200, message="用户已删除")
