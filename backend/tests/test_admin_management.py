"""管理员身份管理与默认管理员初始化测试。"""

from app.core.security import hash_password, verify_password
from app.database.seed import (
    DEFAULT_ADMIN,
    LEGACY_DEFAULT_ADMIN_PASSWORD,
    seed_default_admin,
)
from app.entity.db_models import User, UserRole
from app.services.user_service import user_service


def create_user(db, username, role, *, is_superuser=False):
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("password123"),
        is_active=True,
        is_superuser=is_superuser,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


class TestDefaultAdmin:
    def test_seed_creates_admin_with_requested_password(self, db, seed_rbac):
        admin = seed_default_admin(db, seed_rbac["admin"])

        assert admin.username == DEFAULT_ADMIN["username"]
        assert admin.email == DEFAULT_ADMIN["email"]
        assert verify_password(DEFAULT_ADMIN["password"], admin.hashed_password)
        assert admin.is_superuser is False
        assert user_service.get_user_roles(db, admin) == ["admin"]
        permissions = user_service.get_user_permissions(db, admin)
        assert "user:manage" in permissions
        assert "system:admin" not in permissions

        seed_default_admin(db, seed_rbac["admin"])
        assert db.query(User).filter(User.username == "admin").count() == 1

    def test_seed_only_migrates_legacy_default_password(self, db, seed_rbac):
        admin = User(
            username="admin",
            email="admin@visagent.com",
            hashed_password=hash_password(LEGACY_DEFAULT_ADMIN_PASSWORD),
            is_active=True,
        )
        db.add(admin)
        db.commit()

        seeded = seed_default_admin(db, seed_rbac["admin"])

        assert verify_password(DEFAULT_ADMIN["password"], seeded.hashed_password)
        assert not verify_password(LEGACY_DEFAULT_ADMIN_PASSWORD, seeded.hashed_password)


class TestAdminRoleApi:
    @staticmethod
    def auth_headers(user):
        token = user_service.create_access_token_for_user(user)
        return {"Authorization": f"Bearer {token}"}

    def test_admin_can_promote_normal_user(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        normal_user = create_user(db, "member", seed_rbac["user"])

        response = client.put(
            f"/api/admin/users/{normal_user.id}/role",
            json={"role": "admin"},
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 200
        db.expire_all()
        assert user_service.get_user_roles(db, normal_user) == ["admin"]

    def test_regular_admin_cannot_demote_another_admin(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        target = create_user(db, "othermanager", seed_rbac["admin"])

        response = client.put(
            f"/api/admin/users/{target.id}/role",
            json={"role": "user"},
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 403
        assert response.json()["message"] == "只有超级管理员可以降级管理员"
        assert user_service.get_user_roles(db, target) == ["admin"]

    def test_super_admin_can_demote_another_admin(self, client, db, seed_rbac):
        super_admin = create_user(
            db,
            "supermanager",
            seed_rbac["super_admin"],
        )
        target = create_user(db, "othermanager", seed_rbac["admin"])

        response = client.put(
            f"/api/admin/users/{target.id}/role",
            json={"role": "user"},
            headers=self.auth_headers(super_admin),
        )

        assert response.status_code == 200
        db.expire_all()
        assert user_service.get_user_roles(db, target) == ["user"]
        assert target.is_superuser is False

    def test_normal_user_cannot_change_identity(self, client, db, seed_rbac):
        normal_user = create_user(db, "member", seed_rbac["user"])
        target = create_user(db, "target", seed_rbac["user"])

        response = client.put(
            f"/api/admin/users/{target.id}/role",
            json={"role": "admin"},
            headers=self.auth_headers(normal_user),
        )

        assert response.status_code == 403
        assert user_service.get_user_roles(db, target) == ["user"]

    def test_admin_cannot_change_own_identity(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])

        response = client.put(
            f"/api/admin/users/{admin.id}/role",
            json={"role": "user"},
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 400
        assert response.json()["message"] == "不能修改自身身份"
        assert user_service.get_user_roles(db, admin) == ["admin"]

    def test_identity_only_accepts_admin_or_user(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        target = create_user(db, "target", seed_rbac["user"])

        response = client.put(
            f"/api/admin/users/{target.id}/role",
            json={"role": "super_admin"},
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 422
        assert user_service.get_user_roles(db, target) == ["user"]


class TestAdminUserApi:
    @staticmethod
    def auth_headers(user):
        token = user_service.create_access_token_for_user(user)
        return {"Authorization": f"Bearer {token}"}

    def test_admin_can_create_normal_user(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])

        response = client.post(
            "/api/admin/users",
            json={
                "username": "createduser",
                "email": "created@example.com",
                "password": "password123",
            },
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 201
        created = db.query(User).filter(User.username == "createduser").first()
        assert created is not None
        assert created.is_superuser is False
        assert user_service.get_user_roles(db, created) == ["user"]

    def test_user_search_matches_username_or_email(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        create_user(db, "searchable", seed_rbac["user"])
        create_user(db, "another", seed_rbac["user"])

        response = client.get(
            "/api/admin/users",
            params={"keyword": "search"},
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert [item["username"] for item in items] == ["searchable"]

    def test_admin_can_delete_normal_user(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        target = create_user(db, "member", seed_rbac["user"])

        response = client.delete(
            f"/api/admin/users/{target.id}",
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 200
        assert db.query(User).filter(User.id == target.id).first() is None

    def test_regular_admin_cannot_delete_another_admin(self, client, db, seed_rbac):
        admin = create_user(db, "manager", seed_rbac["admin"])
        target = create_user(db, "othermanager", seed_rbac["admin"])

        response = client.delete(
            f"/api/admin/users/{target.id}",
            headers=self.auth_headers(admin),
        )

        assert response.status_code == 403
        assert response.json()["message"] == "只有超级管理员可以删除管理员"
        assert db.query(User).filter(User.id == target.id).first() is not None

    def test_super_admin_can_delete_another_admin(self, client, db, seed_rbac):
        super_admin = create_user(
            db,
            "supermanager",
            seed_rbac["super_admin"],
        )
        target = create_user(db, "othermanager", seed_rbac["admin"])

        response = client.delete(
            f"/api/admin/users/{target.id}",
            headers=self.auth_headers(super_admin),
        )

        assert response.status_code == 200
        assert db.query(User).filter(User.id == target.id).first() is None
