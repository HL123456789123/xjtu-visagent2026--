"""
系统管理 API 路由
提供用户管理、角色管理、权限管理等接口
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user, RequirePermission, is_super_admin
from app.core.logger import get_logger
from app.database.session import get_db
from app.entity.db_models import User
from app.entity.schemas import (
    ApiResponse,
    UserAdminUpdate,
    UserRoleAssign,
    UserRoleUpdate,
    UserStatusUpdate,
    RoleCreate,
    RoleUpdate,
    RolePermissionAssign,
)
from app.services.user_service import user_service
from app.services.role_service import role_service

logger = get_logger("admin_api")

router = APIRouter(prefix="/api/admin", tags=["系统管理"])


# ══════════════════════════════════════════════════════════════
# 一、用户管理
# ══════════════════════════════════════════════════════════════


@router.get("/users", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:list"))])
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键字（用户名或邮箱）"),
    is_active: bool = Query(None, description="是否启用"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分页查询用户列表"""
    result = user_service.get_user_list(
        db=db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        is_active=is_active,
    )
    return ApiResponse(code=200, data=result)


@router.get("/users/{user_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:list"))])
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户详情"""
    user = user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    roles = user_service.get_user_roles(db, user)
    return ApiResponse(
        code=200,
        data={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "avatar": user.avatar,
            "is_active": user.is_active,
            "is_superuser": is_super_admin(user, db),
            "roles": roles,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        },
    )


@router.put("/users/{user_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:manage"))])
async def update_user(
    user_id: int,
    data: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """管理员修改用户信息"""
    kwargs = data.model_dump(exclude_unset=True)
    if not kwargs:
        raise HTTPException(status_code=400, detail="未提供任何更新字段")

    user_service.admin_update_user(
        db=db,
        user_id=user_id,
        current_user_id=current_user.id,
        **kwargs,
    )
    return ApiResponse(code=200, message="用户信息更新成功")


@router.put("/users/{user_id}/roles", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:manage"))])
async def assign_user_roles(
    user_id: int,
    data: UserRoleAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分配用户角色"""
    user_service.assign_user_roles(
        db=db,
        user_id=user_id,
        role_ids=data.role_ids,
        current_user_id=current_user.id,
    )
    return ApiResponse(code=200, message="用户角色分配成功")


@router.put(
    "/users/{user_id}/role",
    response_model=ApiResponse,
    dependencies=[Depends(RequirePermission("user:manage"))],
)
async def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将用户身份设置为管理员或普通用户。"""
    user_service.set_user_role(
        db=db,
        user_id=user_id,
        role_name=data.role,
        current_user_id=current_user.id,
    )
    role_text = "管理员" if data.role == "admin" else "普通用户"
    return ApiResponse(code=200, message=f"用户身份已设置为{role_text}")


@router.put("/users/{user_id}/status", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:manage"))])
async def toggle_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用/禁用用户"""
    user_service.toggle_user_active(
        db=db,
        user_id=user_id,
        is_active=data.is_active,
        current_user_id=current_user.id,
    )
    status_text = "启用" if data.is_active else "禁用"
    return ApiResponse(code=200, message=f"用户已{status_text}")


@router.delete("/users/{user_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("user:manage"))])
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除用户"""
    user_service.delete_user(
        db=db,
        user_id=user_id,
        current_user_id=current_user.id,
    )
    return ApiResponse(code=200, message="用户已删除")


# ══════════════════════════════════════════════════════════════
# 二、角色管理
# ══════════════════════════════════════════════════════════════


@router.get("/roles", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:list"))])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取角色列表"""
    roles = role_service.get_role_list(db)
    return ApiResponse(code=200, data=roles)


@router.get("/roles/{role_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:list"))])
async def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取角色详情"""
    role = role_service.get_role_detail(db, role_id)
    return ApiResponse(code=200, data=role)


@router.post("/roles", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:manage"))])
async def create_role(
    data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建角色"""
    role = role_service.create_role(
        db=db,
        name=data.name,
        display_name=data.display_name,
        description=data.description,
        permission_codes=data.permission_codes,
    )
    return ApiResponse(
        code=200,
        message="角色创建成功",
        data={"id": role.id, "name": role.name},
    )


@router.put("/roles/{role_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:manage"))])
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新角色"""
    role_service.update_role(
        db=db,
        role_id=role_id,
        display_name=data.display_name,
        description=data.description,
        permission_codes=data.permission_codes,
    )
    return ApiResponse(code=200, message="角色更新成功")


@router.delete("/roles/{role_id}", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:manage"))])
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除角色"""
    role_service.delete_role(db, role_id)
    return ApiResponse(code=200, message="角色已删除")


@router.put("/roles/{role_id}/permissions", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:manage"))])
async def assign_role_permissions(
    role_id: int,
    data: RolePermissionAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """分配角色权限"""
    role_service.assign_role_permissions(
        db=db,
        role_id=role_id,
        permission_codes=data.permission_codes,
    )
    return ApiResponse(code=200, message="角色权限分配成功")


# ══════════════════════════════════════════════════════════════
# 三、权限管理
# ══════════════════════════════════════════════════════════════


@router.get("/permissions", response_model=ApiResponse, dependencies=[Depends(RequirePermission("role:list"))])
async def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有权限列表（按模块分组）"""
    permissions = role_service.get_all_permissions(db)
    return ApiResponse(code=200, data=permissions)
