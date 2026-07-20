"""
用户服务层
处理用户注册、登录、鉴权等业务逻辑
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tz import now_cst
from app.entity.db_models import (
    ChatSession,
    Dataset,
    DetectionScene,
    DetectionTask,
    FoodModelVersion,
    FoodRecognitionTask,
    Model,
    OperationLog,
    Permission,
    Recipe,
    Role,
    RolePermission,
    TrainingTask,
    User,
    UserRole,
)


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

        # 公开注册固定为普通用户，客户端提交的任何角色字段都不会被采用。
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

        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已停用")

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
                "roles": [
                    "super_admin"
                    if "super_admin" in role_map.get(user.id, [])
                    else "admin"
                    if "admin" in role_map.get(user.id, [])
                    else "user"
                ],
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
    def admin_update_user(db: Session, user_id: int, actor: User, **kwargs) -> User:
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
        user = UserService._get_manageable_target(db, user_id, actor)

        # 更新允许的字段
        allowed_fields = {"email", "phone"}
        for key, value in kwargs.items():
            if key in allowed_fields and value is not None:
                setattr(user, key, value)

        UserService._add_operation_log(
            db,
            actor,
            action="update",
            target=user,
            description="更新用户基本信息",
        )

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def set_user_role(
        db: Session,
        user_id: int,
        role_name: str,
        actor: User,
    ) -> User:
        if role_name not in {"user", "admin"}:
            raise HTTPException(status_code=400, detail="角色只允许 user 或 admin")
        user = UserService._get_manageable_target(db, user_id, actor)
        actor_role = UserService.get_product_role(db, actor)
        target_role = UserService.get_product_role(db, user)
        if target_role == "super_admin":
            raise HTTPException(status_code=403, detail="超级管理员角色不可通过此接口修改")
        if actor_role == "admin" and target_role != "user":
            raise HTTPException(status_code=403, detail="管理员不能修改其他管理员")

        role = db.query(Role).filter(Role.name == role_name).first()
        if role is None:
            raise HTTPException(status_code=500, detail="系统角色未初始化")
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()
        db.add(UserRole(user_id=user_id, role_id=role.id))
        UserService._add_operation_log(
            db,
            actor,
            action="change_role",
            target=user,
            description=f"将用户角色从 {target_role} 调整为 {role_name}",
        )
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def toggle_user_active(db: Session, user_id: int, is_active: bool, actor: User) -> User:
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
        if user_id == actor.id:
            raise HTTPException(status_code=400, detail="不能禁用自身账号")

        user = UserService._get_manageable_target(db, user_id, actor)

        user.is_active = is_active
        UserService._add_operation_log(
            db,
            actor,
            action="enable" if is_active else "disable",
            target=user,
            description="启用用户" if is_active else "禁用用户",
        )
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int, actor: User) -> bool:
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
        if user_id == actor.id:
            raise HTTPException(status_code=400, detail="不能删除自身账号")

        user = UserService._get_manageable_target(db, user_id, actor)
        business_references = (
            (DetectionScene, DetectionScene.created_by == user_id),
            (DetectionTask, DetectionTask.user_id == user_id),
            (Model, Model.created_by == user_id),
            (Dataset, Dataset.user_id == user_id),
            (TrainingTask, TrainingTask.user_id == user_id),
            (FoodRecognitionTask, FoodRecognitionTask.user_id == user_id),
            (Recipe, Recipe.user_id == user_id),
            (ChatSession, ChatSession.user_id == user_id),
            (
                FoodModelVersion,
                (FoodModelVersion.uploaded_by == user_id)
                | (FoodModelVersion.activated_by == user_id),
            ),
        )
        has_business_data = any(
            db.query(model.id).filter(condition).first() is not None
            for model, condition in business_references
        )
        if has_business_data:
            raise HTTPException(status_code=409, detail="该用户已有业务数据，请先禁用账号")

        # 删除用户角色关联
        db.query(UserRole).filter(UserRole.user_id == user_id).delete()

        UserService._add_operation_log(
            db,
            actor,
            action="delete",
            target=user,
            description="删除无业务数据的用户",
        )
        db.delete(user)
        db.commit()
        return True

    @staticmethod
    def reset_password(db: Session, user_id: int, new_password: str, actor: User) -> None:
        user = UserService._get_manageable_target(db, user_id, actor)
        user.hashed_password = hash_password(new_password)
        UserService._add_operation_log(
            db,
            actor,
            action="reset_password",
            target=user,
            description="管理员重置用户密码",
        )
        db.commit()

    @staticmethod
    def get_product_role(db: Session, user: User) -> str:
        roles = set(UserService.get_user_roles(db, user))
        if "super_admin" in roles:
            return "super_admin"
        if "admin" in roles:
            return "admin"
        return "user"

    @staticmethod
    def _get_manageable_target(db: Session, user_id: int, actor: User) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        actor_role = UserService.get_product_role(db, actor)
        target_role = UserService.get_product_role(db, user)
        if actor_role not in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="仅管理员可管理用户")
        if target_role == "super_admin":
            raise HTTPException(status_code=403, detail="不能管理超级管理员账号")
        if actor_role == "admin" and target_role == "admin":
            raise HTTPException(status_code=403, detail="管理员不能管理其他管理员")
        return user

    @staticmethod
    def _add_operation_log(
        db: Session,
        actor: User,
        *,
        action: str,
        target: User,
        description: str,
    ) -> None:
        db.add(
            OperationLog(
                user_id=actor.id,
                username=actor.username,
                module="auth",
                action=action,
                target_type="user",
                target_id=str(target.id),
                description=description,
                status="success",
            )
        )


# 全局单例
user_service = UserService()
