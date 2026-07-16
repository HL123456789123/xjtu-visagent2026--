# -*- coding: utf-8 -*-
"""
数据库迁移脚本：移除 users 表的 is_superuser 字段
统一使用 RBAC 角色系统（super_admin 角色）

使用方法：
    cd backend
    python -m app.database.migrate_remove_superuser
"""

import sys
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.logger import get_logger

logger = get_logger("migrate_remove_superuser")


def migrate_remove_superuser(db: Session):
    """
    移除 is_superuser 字段
    
    Args:
        db: 数据库会话
    """
    # 1. 检查字段是否存在
    result = db.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'is_superuser'
    """)).fetchone()
    
    if not result:
        logger.info("is_superuser 字段不存在，无需迁移")
        print("is_superuser 字段不存在，无需迁移")
        return
    
    # 2. 为所有 is_superuser=true 的用户添加 super_admin 角色（如果没有的话）
    logger.info("为 is_superuser=true 的用户添加 super_admin 角色...")
    
    db.execute(text("""
        INSERT INTO user_roles (user_id, role_id, created_at)
        SELECT u.id, r.id, NOW()
        FROM users u, roles r
        WHERE u.is_superuser = true 
            AND r.name = 'super_admin'
            AND NOT EXISTS (
                SELECT 1 FROM user_roles ur 
                WHERE ur.user_id = u.id AND ur.role_id = r.id
            )
    """))
    
    count = db.execute(text("""
        SELECT COUNT(*) FROM users WHERE is_superuser = true
    """)).scalar()
    
    logger.info(f"已为 {count} 个超级管理员用户确保拥有 super_admin 角色")
    
    # 3. 删除 is_superuser 列
    logger.info("删除 is_superuser 列...")
    db.execute(text("ALTER TABLE users DROP COLUMN is_superuser"))
    
    db.commit()
    logger.info("迁移完成：已移除 is_superuser 字段")
    print("迁移完成：已移除 is_superuser 字段")


def main():
    """命令行入口"""
    from app.database.session import SessionLocal
    
    db = SessionLocal()
    try:
        migrate_remove_superuser(db)
        print("迁移完成！")
    except Exception as e:
        logger.error(f"迁移失败: {e}")
        print(f"迁移失败: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
