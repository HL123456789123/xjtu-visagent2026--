from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.database.seed import DEFAULT_USERS, seed_scenes
from app.entity.db_models import Dataset, OperationLog, User, UserRole
from app.services.user_service import UserService


def make_user(db, role, username):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("test-password-2026"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def test_startup_no_longer_creates_predictable_default_accounts():
    assert DEFAULT_USERS == []


def test_startup_disables_only_accounts_matching_the_legacy_seed_fingerprint(db):
    legacy = User(
        username="operator",
        email="operator@visagent.com",
        hashed_password="x",
        is_active=True,
    )
    same_name_real_email = User(
        username="viewer",
        email="owner@example.com",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([legacy, same_name_real_email])
    db.commit()

    seed_scenes(db)

    db.refresh(legacy)
    db.refresh(same_name_real_email)
    assert legacy.is_active is False
    assert same_name_real_email.is_active is True


def test_admin_can_promote_user_but_cannot_manage_another_admin(db, seed_rbac):
    actor = make_user(db, seed_rbac["admin"], "role_admin")
    target = make_user(db, seed_rbac["user"], "role_user")
    other_admin = make_user(db, seed_rbac["admin"], "other_admin")

    UserService.set_user_role(db, target.id, "admin", actor)
    assert UserService.get_product_role(db, target) == "admin"
    assert (
        db.query(OperationLog)
        .filter(OperationLog.action == "change_role", OperationLog.target_id == str(target.id))
        .count()
        == 1
    )

    with pytest.raises(HTTPException, match="管理员不能管理其他管理员"):
        UserService.toggle_user_active(db, other_admin.id, False, actor)


def test_super_admin_can_demote_admin_but_cannot_assign_super_admin(db, seed_rbac):
    actor = make_user(db, seed_rbac["super_admin"], "role_super")
    target = make_user(db, seed_rbac["admin"], "role_target_admin")

    UserService.set_user_role(db, target.id, "user", actor)
    assert UserService.get_product_role(db, target) == "user"

    with pytest.raises(HTTPException, match="只允许 user 或 admin"):
        UserService.set_user_role(db, target.id, "super_admin", actor)


def test_super_admin_cannot_disable_or_delete_self(db, seed_rbac):
    actor = make_user(db, seed_rbac["super_admin"], "self_super")

    with pytest.raises(HTTPException, match="不能禁用自身账号"):
        UserService.toggle_user_active(db, actor.id, False, actor)
    with pytest.raises(HTTPException, match="不能删除自身账号"):
        UserService.delete_user(db, actor.id, actor)


def test_user_with_retained_legacy_business_data_must_be_disabled_not_deleted(db, seed_rbac):
    actor = make_user(db, seed_rbac["super_admin"], "delete_guard_super")
    target = make_user(db, seed_rbac["user"], "delete_guard_user")
    db.add(
        Dataset(
            user_id=target.id,
            name="历史训练集",
            path="/retained/history",
            yaml_path="/retained/history/data.yaml",
        )
    )
    db.commit()

    with pytest.raises(HTTPException, match="已有业务数据"):
        UserService.delete_user(db, target.id, actor)
