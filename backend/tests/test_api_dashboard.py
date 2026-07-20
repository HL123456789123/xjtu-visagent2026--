"""
Dashboard API 测试
测试仪表盘统计数据的正确性和权限控制
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.entity.db_models import Model, User, UserRole
from app.core.security import hash_password


@pytest.fixture
def test_user(db: Session, seed_rbac):
    """创建测试用户（user 角色）"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=hash_password("testpassword"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=seed_rbac["user"].id))
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db: Session, seed_rbac):
    """创建管理员用户（super_admin 角色）"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("adminpassword"),
        is_active=True,
    )
    db.add(admin)
    db.flush()
    # 分配 super_admin 角色
    db.add(UserRole(user_id=admin.id, role_id=seed_rbac["super_admin"].id))
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client: TestClient, test_user):
    """获取普通用户认证"""
    client.cookies.clear()  # 清除之前测试留下的 cookie
    response = client.post("/api/auth/login", json={"username": "testuser", "password": "testpassword"})
    assert response.status_code == 200, f"登录失败: {response.status_code}"
    return {}


@pytest.fixture
def admin_headers(client: TestClient, test_admin):
    """获取管理员认证"""
    client.cookies.clear()  # 清除之前测试留下的 cookie
    response = client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword"})
    assert response.status_code == 200, f"管理员登录失败: {response.status_code}"
    return {}


class TestDashboardStats:
    """仪表盘统计数据测试"""

    def test_get_dashboard_stats_unauthenticated(self, client: TestClient):
        """未认证用户无法获取仪表盘数据"""
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 401

    def test_get_dashboard_stats_authenticated(self, client: TestClient, auth_headers, test_user, db: Session):
        """认证用户可以获取自己的仪表盘数据"""
        # 创建测试数据
        model = Model(
            created_by=test_user.id,
            name="test_model",
            category="general",
            base_architecture="yolo26n",
            class_names=["person", "car"],
            status="active",
            is_enabled=True,
        )
        db.add(model)
        db.commit()

        response = client.get("/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "overview" in data["data"]
        assert "total_models" in data["data"]["overview"]

    def test_get_dashboard_stats_admin_sees_all(self, client: TestClient, admin_headers, test_admin, test_user, db: Session):
        """管理员可以看到所有用户的数据"""
        # 创建普通用户的数据
        model = Model(
            created_by=test_user.id,
            name="user_model",
            category="general",
            base_architecture="yolo26n",
            class_names=["person", "car"],
            status="active",
            is_enabled=True,
        )
        db.add(model)
        db.commit()

        response = client.get("/api/dashboard/stats", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_dashboard_stats_user_only_sees_own(self, client: TestClient, auth_headers, test_user, test_admin, db: Session):
        """普通用户只能看到自己的数据"""
        # 创建管理员的数据
        admin_model = Model(
            created_by=test_admin.id,
            name="admin_model",
            category="general",
            base_architecture="yolo26n",
            class_names=["person", "car"],
            status="active",
            is_enabled=True,
        )
        db.add(admin_model)
        db.commit()

        response = client.get("/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        # 验证不包含管理员的数据
        assert data["data"]["overview"]["total_models"] == 0


class TestDashboardUserStats:
    """用户统计数据测试"""

    def test_get_user_stats(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取用户统计数据"""
        response = client.get("/api/dashboard/user-stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "detections" in data["data"]

    def test_get_user_stats_unauthenticated(self, client: TestClient, db: Session):
        """未认证用户无法获取用户统计"""
        response = client.get("/api/dashboard/user-stats")
        assert response.status_code == 401
