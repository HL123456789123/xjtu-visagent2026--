"""
Training API 测试
测试训练任务的创建、启动、暂停、取消等操作
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.entity.db_models import User, TrainingTask, Dataset
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
def test_dataset(db: Session, test_user):
    """创建测试数据集"""
    dataset = Dataset(
        user_id=test_user.id,
        name="test_dataset",
        path="/tmp/test_dataset",
        description="测试数据集",
        num_images=100,
        num_classes=5,
        status="ready",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@pytest.fixture
def auth_headers(client: TestClient, test_user):
    """获取认证头"""
    client.post("/api/auth/login", json={"username": "testuser", "password": "testpassword"})
    return {}


class TestTrainingTaskCreation:
    """训练任务创建测试"""

    def test_create_training_task(self, client: TestClient, auth_headers, test_dataset):
        """创建训练任务"""
        task_data = {
            "model_name": "yolo26n",
            "epochs": 10,
            "batch_size": 8,
            "lr0": 0.01,
            "device": "cpu",
            "dataset_id": test_dataset.id,
        }
        response = client.post("/api/training/tasks", json=task_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["status"] == "pending"

    def test_create_training_task_without_auth(self, client: TestClient):
        """未认证用户无法创建训练任务"""
        task_data = {
            "model_name": "yolo26n",
            "epochs": 10,
            "batch_size": 8,
            "lr0": 0.01,
            "device": "cpu",
            "dataset_id": 1,
        }
        response = client.post("/api/training/tasks", json=task_data)
        assert response.status_code == 401

    def test_create_training_task_invalid_dataset(self, client: TestClient, auth_headers):
        """使用不存在的数据集创建训练任务"""
        task_data = {
            "model_name": "yolo26n",
            "epochs": 10,
            "batch_size": 8,
            "lr0": 0.01,
            "device": "cpu",
            "dataset_id": 99999,
        }
        response = client.post("/api/training/tasks", json=task_data, headers=auth_headers)
        assert response.status_code == 400


class TestTrainingTaskOperations:
    """训练任务操作测试"""

    def test_get_training_tasks(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取训练任务列表"""
        # 创建测试任务
        task = TrainingTask(
            user_id=test_user.id,
            model_name="yolo26n",
            epochs=10,
            batch_size=8,
            status="pending",
        )
        db.add(task)
        db.commit()

        response = client.get("/api/training/tasks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "items" in data["data"]

    def test_get_training_task_detail(self, client: TestClient, auth_headers, test_user, db: Session):
        """获取训练任务详情"""
        task = TrainingTask(
            user_id=test_user.id,
            model_name="yolo26n",
            epochs=10,
            batch_size=8,
            status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        response = client.get(f"/api/training/tasks/{task.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == task.id

    def test_delete_training_task(self, client: TestClient, auth_headers, test_user, db: Session):
        """删除训练任务"""
        task = TrainingTask(
            user_id=test_user.id,
            model_name="yolo26n",
            epochs=10,
            batch_size=8,
            status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        response = client.delete(f"/api/training/tasks/{task.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200


class TestTrainingTaskPermissions:
    """训练任务权限测试"""

    def test_user_cannot_access_other_user_task(self, client: TestClient, auth_headers, test_user, db: Session):
        """用户无法访问其他用户的任务"""
        # 创建另一个用户
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=get_password_hash("otherpassword"),
            is_active=True,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        # 创建其他用户的任务
        task = TrainingTask(
            user_id=other_user.id,
            model_name="yolo26n",
            epochs=10,
            batch_size=8,
            status="pending",
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 尝试访问其他用户的任务
        response = client.get(f"/api/training/tasks/{task.id}", headers=auth_headers)
        assert response.status_code == 403
