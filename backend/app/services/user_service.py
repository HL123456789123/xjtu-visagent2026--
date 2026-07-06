"""
用户服务层
处理用户注册、登录、鉴权等业务逻辑
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password, verify_password
from app.entity.db_models import User, UserRole, Role


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

        # 自动分配 operator 角色
        operator_role = db.query(Role).filter(Role.name == "operator").first()
        if operator_role:
            db.add(UserRole(user_id=new_user.id, role_id=operator_role.id))

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
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        """根据 ID 获取用户，不存在则返回 None"""
        return db.query(User).filter(User.id == user_id).first()


# 全局单例
user_service = UserService()
