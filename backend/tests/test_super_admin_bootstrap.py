import pytest

from app.core.security import verify_password
from app.entity.db_models import OperationLog, User, UserRole
from app.services.super_admin_bootstrap import (
    SuperAdminBootstrapError,
    bootstrap_super_admin,
)


def test_bootstrap_creates_first_super_admin(db, seed_rbac):
    result = bootstrap_super_admin(
        db,
        username="first_owner",
        email="first_owner@example.com",
        password="StrongPassword2026",
    )

    user = db.query(User).filter(User.id == result.user_id).one()
    role_link = db.query(UserRole).filter(UserRole.user_id == user.id).one()

    assert result.created is True
    assert role_link.role_id == seed_rbac["super_admin"].id
    assert verify_password("StrongPassword2026", user.hashed_password)
    assert (
        db.query(OperationLog)
        .filter(
            OperationLog.action == "bootstrap_super_admin",
            OperationLog.target_id == str(user.id),
        )
        .count()
        == 1
    )


def test_bootstrap_promotes_existing_active_user(db, seed_rbac):
    user = User(
        username="existing_owner",
        email="existing_owner@example.com",
        hashed_password="already-hashed",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=seed_rbac["user"].id))
    db.commit()

    result = bootstrap_super_admin(db, username=user.username)

    role_links = db.query(UserRole).filter(UserRole.user_id == user.id).all()
    assert result.created is False
    assert [link.role_id for link in role_links] == [seed_rbac["super_admin"].id]


def test_bootstrap_refuses_when_active_super_admin_exists(db, seed_rbac):
    owner = User(
        username="current_owner",
        email="current_owner@example.com",
        hashed_password="already-hashed",
        is_active=True,
    )
    db.add(owner)
    db.flush()
    db.add(UserRole(user_id=owner.id, role_id=seed_rbac["super_admin"].id))
    db.commit()

    with pytest.raises(SuperAdminBootstrapError, match="already exists"):
        bootstrap_super_admin(
            db,
            username="second_owner",
            email="second_owner@example.com",
            password="AnotherStrongPassword2026",
        )

    assert db.query(User).filter(User.username == "second_owner").first() is None


def test_bootstrap_rejects_weak_password(db, seed_rbac):
    with pytest.raises(SuperAdminBootstrapError, match="at least 12"):
        bootstrap_super_admin(
            db,
            username="weak_owner",
            email="weak_owner@example.com",
            password="weak1",
        )

    assert db.query(User).filter(User.username == "weak_owner").first() is None
