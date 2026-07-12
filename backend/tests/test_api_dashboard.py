"""
Dashboard API 测试
测试仪表盘统计数据的正确性和权限控制
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.entity.db_models import User, TrainingTask, Model, SceneModel, Dataset
from app.core.security import get_password_hash


@pytest.fixture
def test_user(db: Session):
    """创建测试用户"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db: Session):
    """创建管理员用户"""
    admin = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("adminpassword"),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client: TestClient, test_user):
    """获取普通用户认证头"""
    client.post("/api/auth/login", json={"username": "testuser", "password": "testpassword"})
    return {}


@pytest.fixture
def admin_headers(client: TestClient, test_admin):
    """获取管理员认证头"""
    client.post("/api/auth/login", json={"username": "admin", "password": "adminpassword"})
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
            user_id=test_user.id,
            name="test_model",
            category="general",
            base_architecture="yolo26n",
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
        assert "models_count" in data["data"]

    def test_get_dashboard_stats_admin_sees_all(self, client: TestClient, admin_headers, test_admin, test_user, db: Session):
        """管理员可以看到所有用户的数据"""
        # 创建普通用户的数据
        model = Model(
            user_id=test_user.id,
            name="user_model",
            category="general",
            base_architecture="yolo26n",
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
            user_id=test_admin.id,
            name="admin_model",
            category="general",
            base_architecture="yolo26n",
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
        assert data["data"]["models_count"] == 0


class TestDashboardRecentActivities:
    """最近活动测试"""

    def test_get_recent_activities(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取最近活动列表"""
        response = client.get("/api/dashboard/activities", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data

    def test_get_recent_activities_with_limit(self, client: TestClient, auth_headers, test_user, db: Session):
        """限制返回的活动数量"""
        response = client.get("/api/dashboard/activities?limit=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestDashboardCharts:
    """图表数据测试"""

    def test_get_training_trend(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取训练趋势数据"""
        response = client.get("/api/dashboard/training-trend", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

    def test_get_model_distribution(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取模型分布数据"""
        response = client.get("/api/dashboard/model-distribution", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
