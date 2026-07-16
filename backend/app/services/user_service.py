"""
用户服务层
处理用户注册、登录、鉴权等业务逻辑
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tz import now_cst
from app.entity.db_models import User, UserRole, Role, RolePermission, Permission


class UserService:
    """用户服务"""

    @staticmethod
    def register(db: Session, username: str, email: str, password: str) -> User:
        """
        用户注册

        Args:
            db: 数据库会话
            username: 用户名
            email: 邮箱
            password: 明文密码

        Returns:
            新创建的用户对象

        Raises:
            HTTPException: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="邮箱已被注册")

        # 创建新用户
        new_user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
        )
        db.add(new_user)
        db.flush()

        # 公开注册只能成为普通用户，管理员身份必须由管理员后续授予。
        user_role = db.query(Role).filter(Role.name == "user").first()
        if user_role:
            db.add(UserRole(user_id=new_user.id, role_id=user_role.id))

        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def login(db: Session, username: str, password: str) -> User:
        """
        用户登录

        Args:
            db: 数据库会话
            username: 用户名
            password: 明文密码

        Returns:
            登录成功的用户对象

        Raises:
            HTTPException: 用户名或密码错误
        """
        user = db.query(User).filter((User.username == username) | (User.email == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        if not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 更新最后登录时间
        user.last_login_at = now_cst()
        db.commit()

        return user

    @staticmethod
    def create_access_token_for_user(user: User) -> str:
        """为用户生成 JWT Token"""
        return create_access_token(data={"sub": str(user.id)})

    @staticmethod
    def get_user_roles(db: Session, user: User) -> list[str]:
        """获取用户的角色标识列表

        直接查询数据库，避免依赖 User 对象的 lazy-loaded 关系，
        防止在 User 对象 detached 后访问 user_roles 时抛出 DetachedInstanceError。
        """
        roles = (
            db.query(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id)
            .all()
        )
        return [role[0] for role in roles]

    @staticmethod
    def get_user_permissions(db: Session, user: User) -> list[str]:
        """获取用户通过角色关联的所有权限编码列表

        超级管理员返回 None 表示拥有所有权限（前端特殊处理）。
        """
        from app.core.security import is_super_admin

        if is_super_admin(user, db):
            return ["*"]  # 前端约定：'*' 表示拥有所有权限

        perms = (
            db.query(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .filter(UserRole.user_id == user.id)
            .distinct()
            .all()
        )
        return [p[0] for p in perms]

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        """根据 ID 获取用户，不存在则返回 None"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_user_list(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> dict:
        """
        分页查询用户列表

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            keyword: 搜索关键字（用户名或邮箱）
            is_active: 是否启用筛选

        Returns:
            分页结果字典
        """
        query = db.query(User)

        # 关键字搜索（转义 LIKE 通配符，防止用户输入 % 或 _ 导致非预期匹配）
        if keyword:
            escaped = keyword.replace("%", "\\%").replace("_", "\\_")
            query = query.filter(
                (User.username.ilike(f"%{escaped}%", escape="\\"))
                | (User.email.ilike(f"%{escaped}%", escape="\\"))
            )

        # 状态筛选
        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        # 计算总数
        total = query.count()

        # 分页查询
        users = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # 批量查询所有用户的角色（避免 N+1）
        user_ids = [u.id for u in users]
        role_map: dict[int, list[str]] = {uid: [] for uid in user_ids}
        if user_ids:
            rows = (
                db.query(UserRole.user_id, Role.name)
                .join(Role, UserRole.role_id == Role.id)
                .filter(UserRole.user_id.in_(user_ids))
                .all()
            )
            for uid, rname in rows:
                role_map[uid].append(rname)

        # 组装结果
        items = []
        for user in users:
            items.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "avatar": user.avatar,
                "is_active": user.is_active,
                "roles": role_map.get(user.id, []),
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "items": items,
        }

    @staticmethod
    def admin_update_user(db: Session, user_id: int, current_user_id: int, **kwargs) -> User:
        """
        管理员修改用户信息

        Args:
            db: 数据库会话
            user_id: 目标用户 ID
            current_user_id: 当前操作用户 ID
            **kwargs: 要更新的字段

        Returns:
            更新后的用户对象

        Raises:
            HTTPException: 用户不存在或禁止操作
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 更新允许的字段
        allowed_fields = {"email", "phone", "is_active"}
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(user, key, value)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def assign_user_roles(
        db: Session,
        user_id: int,
        role_ids: list[int],
        current_user_id: int,
    ) -> User:
        """
        分配用户角色（替换式）

        Args:
            db: 数据库会话
            user_id: 用户 ID
            role_ids: 角色 ID 列表
            current_user_id: 当前操作用户 ID

        Returns:
            更新后的用户对象

        Raises:
            HTTPException: 用户不存在或角色不存在
        """
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="不能修改自身身份")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if len(role_ids) != 1:
            raise HTTPException(status_code=400, detail="用户必须且只能选择一种身份")

        # 校验角色是否存在
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
        if len(roles) != len(role_ids):
            found_ids = {r.id for r in roles}
            missing_ids = [rid for rid in role_ids if rid not in found_ids]
            raise HTTPException(status_code=400, detail=f"角色不存在: {missing_ids}")
        if roles[0].name not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="用户身份只能是管理员或普通用户")

        # 删除旧角色关联
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()

        # 添加新角色关联
        for role_id in role_ids:
            db.add(UserRole(user_id=user_id, role_id=role_id))

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def set_user_role(
        db: Session,
        user_id: int,
        role_name: str,
        current_user_id: int,
    ) -> User:
        """将用户身份设置为管理员或普通用户。"""
        if role_name not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="用户身份只能是管理员或普通用户")
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="不能修改自身身份")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            raise HTTPException(status_code=500, detail=f"系统角色未初始化: {role_name}")

        # 身份为二选一：清除旧关联后只保留 admin 或 user 中的一个。
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        db.add(UserRole(user_id=user_id, role_id=role.id))
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def toggle_user_active(db: Session, user_id: int, is_active: bool, current_user_id: int) -> User:
        """
        启用/禁用用户

        Args:
            db: 数据库会话
            user_id: 用户 ID
            is_active: 是否启用
            current_user_id: 当前操作用户 ID

        Returns:
            更新后的用户对象

        Raises:
            HTTPException: 禁止操作自身
        """
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="不能禁用自身账号")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        user.is_active = is_active
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int, current_user_id: int) -> bool:
        """
        删除用户

        Args:
            db: 数据库会话
            user_id: 用户 ID
            current_user_id: 当前操作用户 ID

        Returns:
            是否删除成功

        Raises:
            HTTPException: 禁止删除自身
        """
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="不能删除自身账号")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 删除用户角色关联
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()

        # 删除用户
        db.delete(user)
        db.commit()
        return True


# 全局单例
user_service = UserService()
