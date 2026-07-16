# -*- coding: utf-8 -*-
"""
数据库增量迁移脚本
用于已有部署的环境补充新的角色和权限数据

使用方法：
    cd backend
    python -m app.database.migrate_rbac

执行后会自动检查并补充：
1. 新增的权限（user:list, user:manage, role:list, role:manage）
2. 新增的角色（super_admin, user）
3. 角色权限关联
4. 将现有admin用户提升为super_admin
"""

import sys
from sqlalchemy.orm import Session
from app.core.logger import get_logger

logger = get_logger("migrate_rbac")


def migrate_rbac(db: Session):
    """
    执行 RBAC 增量迁移
    
    Args:
        db: 数据库会话
    """
    from app.entity.db_models import Role, Permission, RolePermission, UserRole, User
    
    # ── 1. 补充新权限 ─────────────────────────────────────
    new_permissions = [
        {"code": "user:list", "name": "查看用户列表", "module": "auth"},
        {"code": "user:manage", "name": "管理用户", "module": "auth"},
        {"code": "role:list", "name": "查看角色列表", "module": "auth"},
        {"code": "role:manage", "name": "管理角色", "module": "auth"},
        {"code": "system:manager_access", "name": "进入管理者入口", "module": "system"},
    ]
    
    existing_perms = {p.code for p in db.query(Permission).all()}
    added_perms = 0
    
    for perm_data in new_permissions:
        if perm_data["code"] not in existing_perms:
            perm = Permission(**perm_data)
            db.add(perm)
            added_perms += 1
            logger.info(f"新增权限: {perm_data['code']}")
    
    if added_perms > 0:
        db.commit()
        logger.info(f"共新增 {added_perms} 个权限")
    else:
        logger.info("权限已存在，无需补充")
    
    # 重新加载权限映射
    perm_map = {p.code: p for p in db.query(Permission).all()}
    
    # ── 2. 补充新角色 ─────────────────────────────────────
    new_roles = [
        {
            "name": "super_admin",
            "display_name": "超级管理员",
            "description": "系统最高权限角色，拥有所有权限",
            "is_system": True,
        },
        {
            "name": "user",
            "display_name": "普通用户",
            "description": "普通用户，拥有基础业务使用权限",
            "is_system": True,
        },
    ]
    
    existing_roles = {r.name for r in db.query(Role).all()}
    added_roles = 0
    role_map = {}
    
    for role_data in new_roles:
        if role_data["name"] not in existing_roles:
            role = Role(**role_data)
            db.add(role)
            db.flush()
            role_map[role_data["name"]] = role
            added_roles += 1
            logger.info(f"新增角色: {role_data['display_name']}")
        else:
            role_map[role_data["name"]] = db.query(Role).filter(Role.name == role_data["name"]).first()
    
    if added_roles > 0:
        db.commit()
        logger.info(f"共新增 {added_roles} 个角色")
    else:
        logger.info("角色已存在，无需补充")
    
    # ── 3. 补充角色权限关联 ────────────────────────────────
    # super_admin 拥有所有权限
    all_perm_codes = list(perm_map.keys())
    
    # admin 拥有除 system:admin 外的所有权限
    admin_perm_codes = [code for code in all_perm_codes if code != "system:admin"]
    
    # user 角色权限
    user_perm_codes = [
        "detection:task:view",
        "training:task:view",
        "model:view",
        "agent:chat",
        "knowledge:search",
    ]
    
    role_perms_config = {
        "super_admin": all_perm_codes,
        "admin": admin_perm_codes,
        "user": user_perm_codes,
    }
    
    added_role_perms = 0
    
    for role_name, perm_codes in role_perms_config.items():
        role = role_map.get(role_name) or db.query(Role).filter(Role.name == role_name).first()
        if not role:
            continue
        
        # 获取已有权限
        existing_perm_ids = {
            rp.permission_id
            for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
        }
        
        # 补充缺失的权限
        for code in perm_codes:
            perm = perm_map.get(code)
            if perm and perm.id not in existing_perm_ids:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
                added_role_perms += 1
    
    if added_role_perms > 0:
        db.commit()
        logger.info(f"共新增 {added_role_perms} 个角色权限关联")
    else:
        logger.info("角色权限关联已存在，无需补充")
    
    # ── 4. 将现有admin用户提升为super_admin ────────────────
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
    
    if admin_role and super_admin_role:
        # 查找拥有admin角色的用户
        admin_user_ids = [
            ur.user_id
            for ur in db.query(UserRole).filter(UserRole.role_id == admin_role.id).all()
        ]
        
        upgraded_count = 0
        for user_id in admin_user_ids:
            # 检查是否已有super_admin角色
            has_super_admin = db.query(UserRole).filter(
                UserRole.user_id == user_id,
                UserRole.role_id == super_admin_role.id,
            ).first()
            
            if not has_super_admin:
                # 添加super_admin角色
                db.add(UserRole(user_id=user_id, role_id=super_admin_role.id))
                
                # 设置is_superuser标志
                user = db.query(User).filter(User.id == user_id).first()
                if user and not user.is_superuser:
                    user.is_superuser = True
                
                upgraded_count += 1
                logger.info(f"用户 {user_id} 已提升为超级管理员")
        
        if upgraded_count > 0:
            db.commit()
            logger.info(f"共提升 {upgraded_count} 个用户为超级管理员")
        else:
            logger.info("无需提升用户权限")
    
    logger.info("RBAC 增量迁移完成")


def main():
    """命令行入口"""
    from app.database.session import SessionLocal
    
    db = SessionLocal()
    try:
        migrate_rbac(db)
        print("迁移完成！")
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        print(f"迁移失败: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
