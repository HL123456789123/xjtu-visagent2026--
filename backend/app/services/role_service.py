"""
角色服务层
处理角色管理、权限分配等业务逻辑
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.entity.db_models import Role, Permission, RolePermission, UserRole


class RoleService:
    """角色服务"""

    @staticmethod
    def get_role_list(db: Session) -> list[dict]:
        """
        获取所有角色列表

        Args:
            db: 数据库会话

        Returns:
            角色列表（包含权限和用户数）
        """
        roles = db.query(Role).order_by(Role.id).all()

        result = []
        for role in roles:
            # 获取角色权限
            permissions = (
                db.query(Permission.code)
                .join(RolePermission, RolePermission.permission_id == Permission.id)
                .filter(RolePermission.role_id == role.id)
                .all()
            )
            perm_codes = [p[0] for p in permissions]

            # 获取关联用户数
            user_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()

            result.append({
                "id": role.id,
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "is_system": role.is_system,
                "permissions": perm_codes,
                "user_count": user_count,
                "created_at": role.created_at,
            })

        return result

    @staticmethod
    def get_role_detail(db: Session, role_id: int) -> dict:
        """
        获取角色详情

        Args:
            db: 数据库会话
            role_id: 角色 ID

        Returns:
            角色详情字典

        Raises:
            HTTPException: 角色不存在
        """
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 获取角色权限
        permissions = (
            db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role.id)
            .all()
        )

        # 获取关联用户数
        user_count = db.query(UserRole).filter(UserRole.role_id == role.id).count()

        return {
            "id": role.id,
            "name": role.name,
            "display_name": role.display_name,
            "description": role.description,
            "is_system": role.is_system,
            "permissions": [p.code for p in permissions],
            "user_count": user_count,
            "created_at": role.created_at,
        }

    @staticmethod
    def create_role(
        db: Session,
        name: str,
        display_name: str,
        description: str | None = None,
        permission_codes: list[str] | None = None,
    ) -> Role:
        """
        创建角色

        Args:
            db: 数据库会话
            name: 角色标识
            display_name: 角色显示名
            description: 角色描述
            permission_codes: 权限编码列表

        Returns:
            新创建的角色对象

        Raises:
            HTTPException: 角色标识已存在或权限不存在
        """
        # 检查角色标识是否已存在
        existing = db.query(Role).filter(Role.name == name).first()
        if existing:
            raise HTTPException(status_code=400, detail="角色标识已存在")

        # 创建角色
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            is_system=False,  # 用户创建的角色非系统角色
        )
        db.add(role)
        db.flush()

        # 分配权限
        if permission_codes:
            RoleService._assign_permissions(db, role.id, permission_codes)

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def update_role(
        db: Session,
        role_id: int,
        display_name: str | None = None,
        description: str | None = None,
        permission_codes: list[str] | None = None,
    ) -> Role:
        """
        更新角色

        Args:
            db: 数据库会话
            role_id: 角色 ID
            display_name: 角色显示名
            description: 角色描述
            permission_codes: 权限编码列表

        Returns:
            更新后的角色对象

        Raises:
            HTTPException: 角色不存在
        """
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 更新基本信息
        if display_name is not None:
            role.display_name = display_name
        if description is not None:
            role.description = description

        # 更新权限
        if permission_codes is not None:
            # 删除旧权限关联
            db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
            # 分配新权限
            RoleService._assign_permissions(db, role_id, permission_codes)

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def delete_role(db: Session, role_id: int) -> bool:
        """
        删除角色

        Args:
            db: 数据库会话
            role_id: 角色 ID

        Returns:
            是否删除成功

        Raises:
            HTTPException: 角色不存在、系统角色不可删除、角色有用户绑定
        """
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 系统角色不可删除
        if role.is_system:
            raise HTTPException(status_code=400, detail="系统内置角色不可删除")

        # 检查是否有用户绑定
        user_count = db.query(UserRole).filter(UserRole.role_id == role_id).count()
        if user_count > 0:
            raise HTTPException(status_code=400, detail=f"该角色下有 {user_count} 个用户，请先解除绑定")

        # 删除角色权限关联
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # 删除角色
        db.delete(role)
        db.commit()
        return True

    @staticmethod
    def assign_role_permissions(db: Session, role_id: int, permission_codes: list[str]) -> Role:
        """
        分配角色权限（替换式）

        Args:
            db: 数据库会话
            role_id: 角色 ID
            permission_codes: 权限编码列表

        Returns:
            更新后的角色对象

        Raises:
            HTTPException: 角色不存在
        """
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="角色不存在")

        # 删除旧权限关联
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # 分配新权限
        RoleService._assign_permissions(db, role_id, permission_codes)

        db.commit()
        db.refresh(role)
        return role

    @staticmethod
    def get_all_permissions(db: Session) -> list[dict]:
        """
        获取所有权限（按模块分组）

        Args:
            db: 数据库会话

        Returns:
            按模块分组的权限列表
        """
        permissions = db.query(Permission).order_by(Permission.module, Permission.code).all()

        # 按模块分组
        modules: dict[str, list] = {}
        for perm in permissions:
            if perm.module not in modules:
                modules[perm.module] = []
            modules[perm.module].append({
                "id": perm.id,
                "code": perm.code,
                "name": perm.name,
                "module": perm.module,
                "description": perm.description,
            })

        # 转换为列表格式
        result = []
        for module, perms in modules.items():
            result.append({
                "module": module,
                "permissions": perms,
            })

        return result

    @staticmethod
    def _assign_permissions(db: Session, role_id: int, permission_codes: list[str]):
        """
        内部方法：分配权限

        Args:
            db: 数据库会话
            role_id: 角色 ID
            permission_codes: 权限编码列表

        Raises:
            HTTPException: 权限不存在
        """
        if not permission_codes:
            return

        # 查询权限
        permissions = db.query(Permission).filter(Permission.code.in_(permission_codes)).all()
        perm_map = {p.code: p for p in permissions}

        # 校验权限是否存在
        missing_codes = [code for code in permission_codes if code not in perm_map]
        if missing_codes:
            raise HTTPException(status_code=400, detail=f"权限不存在: {missing_codes}")

        # 创建角色权限关联
        for code in permission_codes:
            perm = perm_map[code]
            db.add(RolePermission(role_id=role_id, permission_id=perm.id))


# 全局单例
role_service = RoleService()
