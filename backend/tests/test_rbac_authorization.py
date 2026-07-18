"""V1.1 integration RBAC behavior tests.

These tests create only per-test users, roles, and permissions.  They do not
depend on, reveal, or modify production seed credentials.
"""

from __future__ import annotations

import secrets

from app.core.security import create_access_token, hash_password
from app.entity.db_models import Permission, Role, RolePermission, User, UserRole
from app.services.user_service import user_service


def _unique(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _role_with_permissions(db, role_name: str, permission_codes: set[str]) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        role = Role(
            name=role_name,
            display_name=role_name,
            description="test-only role",
            is_system=False,
        )
        db.add(role)
        db.flush()

    existing_codes = {
        permission.code
        for permission in db.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == role.id)
        .all()
    }
    for code in permission_codes - existing_codes:
        permission = db.query(Permission).filter(Permission.code == code).first()
        if permission is None:
            permission = Permission(code=code, name=code, module="test")
            db.add(permission)
            db.flush()
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))
    db.commit()
    return role


def _user_with_role(db, role_name: str, permission_codes: set[str]) -> User:
    role = _role_with_permissions(db, role_name, permission_codes)
    username = _unique("rbac")
    user = User(
        username=username,
        email=f"{username}@example.test",
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = user_service.create_access_token_for_user(user)
    return {"Authorization": f"Bearer {token}"}


def test_registration_ignores_submitted_admin_role_and_assigns_only_viewer(db, client):
    """A public register request cannot self-assign the administrator role."""
    _role_with_permissions(db, "viewer", set())
    username = _unique("registered")

    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.test",
            "password": secrets.token_urlsafe(24),
            "roles": ["admin"],
            "is_superuser": True,
        },
    )

    assert response.status_code == 201
    user = db.query(User).filter(User.username == username).one()
    assert user_service.get_user_roles(db, user) == ["viewer"]
    assert "admin" not in user_service.get_user_roles(db, user)


def test_regular_user_receives_403_from_administrator_api(db, client):
    user = _user_with_role(db, _unique("viewer"), set())

    response = client.get("/api/admin/users", headers=_auth_headers(user))

    assert response.status_code == 403


def test_user_with_user_list_permission_can_access_administrator_api(db, client):
    admin = _user_with_role(db, _unique("admin"), {"user:list"})

    response = client.get("/api/admin/users", headers=_auth_headers(admin))

    assert response.status_code == 200


def test_forged_role_claim_in_token_cannot_escalate_database_permissions(db, client):
    user = _user_with_role(db, _unique("viewer"), set())
    forged_token = create_access_token(
        {
            "sub": str(user.id),
            "roles": ["super_admin"],
            "permissions": ["*"],
        }
    )

    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code == 403


def test_revoking_database_permission_blocks_an_old_token_immediately(db, client):
    admin = _user_with_role(db, _unique("admin"), {"user:list"})
    old_headers = _auth_headers(admin)

    assert client.get("/api/admin/users", headers=old_headers).status_code == 200

    db.query(UserRole).filter(UserRole.user_id == admin.id).delete()
    db.commit()

    assert client.get("/api/admin/users", headers=old_headers).status_code == 403
