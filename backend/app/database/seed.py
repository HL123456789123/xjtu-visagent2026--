"""Incrementally seed the fixed product roles without creating user accounts."""

from app.core.logger import get_logger

logger = get_logger("seed")

DEFAULT_ROLES = [
    {
        "name": "super_admin",
        "display_name": "超级管理员",
        "description": "系统最高权限角色，拥有全部管理能力",
        "is_system": True,
    },
    {
        "name": "admin",
        "display_name": "管理员",
        "description": "可管理普通用户和 Food 推理模型",
        "is_system": True,
    },
    {
        "name": "user",
        "display_name": "普通用户",
        "description": "可使用食材识别、菜谱、对话、历史和个人看板",
        "is_system": True,
    },
]

DEFAULT_PERMISSIONS = [
    {"code": "user:list", "name": "查看用户列表", "module": "auth"},
    {"code": "user:manage", "name": "管理用户", "module": "auth"},
    {"code": "model:create", "name": "上传模型", "module": "model"},
    {"code": "model:update", "name": "启用或回滚模型", "module": "model"},
    {"code": "model:delete", "name": "删除模型", "module": "model"},
    {"code": "model:view", "name": "查看模型", "module": "model"},
    {"code": "agent:chat", "name": "智能对话", "module": "agent"},
    {"code": "system:dashboard", "name": "查看数据看板", "module": "system"},
]

SUPER_ADMIN_PERMISSIONS = [item["code"] for item in DEFAULT_PERMISSIONS]
ADMIN_PERMISSIONS = [
    "user:list",
    "user:manage",
    "model:create",
    "model:update",
    "model:delete",
    "model:view",
    "agent:chat",
    "system:dashboard",
]
USER_PERMISSIONS = ["agent:chat", "system:dashboard"]

ROLE_PERMISSIONS_MAP = {
    "super_admin": SUPER_ADMIN_PERMISSIONS,
    "admin": ADMIN_PERMISSIONS,
    "user": USER_PERMISSIONS,
}

# Existing privileged users are managed deliberately; startup never creates a
# predictable account or password.
DEFAULT_USERS: list[dict[str, str]] = []


def seed_scenes(db_session) -> int:
    """Keep the historical entry point while seeding only fixed roles and permissions."""
    from app.entity.db_models import OperationLog, Permission, Role, RolePermission, User

    permissions = {item.code: item for item in db_session.query(Permission).all()}
    new_permissions = 0
    for definition in DEFAULT_PERMISSIONS:
        if definition["code"] in permissions:
            continue
        permission = Permission(**definition)
        db_session.add(permission)
        db_session.flush()
        permissions[definition["code"]] = permission
        new_permissions += 1

    roles = {item.name: item for item in db_session.query(Role).all()}
    new_roles = 0
    for definition in DEFAULT_ROLES:
        if definition["name"] in roles:
            continue
        role = Role(**definition)
        db_session.add(role)
        db_session.flush()
        roles[definition["name"]] = role
        new_roles += 1

    new_links = 0
    for role_name, permission_codes in ROLE_PERMISSIONS_MAP.items():
        role = roles[role_name]
        linked_ids = {
            link.permission_id
            for link in db_session.query(RolePermission)
            .filter(RolePermission.role_id == role.id)
            .all()
        }
        for code in permission_codes:
            permission = permissions[code]
            if permission.id in linked_ids:
                continue
            db_session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            new_links += 1

    legacy_accounts = (
        db_session.query(User)
        .filter(User.username.in_(("admin", "operator", "user", "viewer")))
        .all()
    )
    disabled_accounts = 0
    for user in legacy_accounts:
        if user.email != f"{user.username}@visagent.com" or not user.is_active:
            continue
        user.is_active = False
        db_session.add(
            OperationLog(
                user_id=None,
                username="system",
                module="auth",
                action="disable_legacy_seed",
                target_type="user",
                target_id=str(user.id),
                description="停用历史可预测默认账号，等待超级管理员复核",
                status="success",
            )
        )
        disabled_accounts += 1

    db_session.commit()
    if new_permissions or new_roles or new_links or disabled_accounts:
        logger.info(
            "核心权限初始化完成: permissions=%s roles=%s links=%s disabled_accounts=%s",
            new_permissions,
            new_roles,
            new_links,
            disabled_accounts,
        )
    else:
        logger.info("核心角色和权限已存在，跳过初始化")
    logger.info("未创建默认账号；历史默认账号已按指纹停用，旧业务种子已停用")
    return 0
