"""
数据库模型测试：CRUD 操作、关系、约束
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.entity.db_models import (
    User, Role, Permission, UserRole, RolePermission,
    DetectionScene, DetectionTask, DetectionResult,
    Model, SceneModel, TrainingTask, TrainingMetric, ModelVersion,
    ChatSession, ChatMessage, OperationLog,
)


class TestUserModel:
    """User 模型测试"""

    def test_create_user(self, db):
        """创建用户基本字段"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_xxx",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.created_at is not None

    def test_username_unique_constraint(self, db):
        """用户名唯一约束"""
        db.add(User(username="unique1", email="a@example.com", hashed_password="hash"))
        db.commit()
        db.add(User(username="unique1", email="b@example.com", hashed_password="hash"))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_email_unique_constraint(self, db):
        """邮箱唯一约束"""
        db.add(User(username="user_a", email="same@example.com", hashed_password="hash"))
        db.commit()
        db.add(User(username="user_b", email="same@example.com", hashed_password="hash"))
        with pytest.raises(IntegrityError):
            db.commit()

    def test_inactive_user(self, db):
        """禁用用户标记"""
        user = User(
            username="disabled",
            email="disabled@example.com",
            hashed_password="hash",
            is_active=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        assert user.is_active is False


class TestRoleModel:
    """Role & Permission 模型测试"""

    def test_create_role(self, db):
        """创建角色"""
        role = Role(name="admin", display_name="管理员", description="系统管理员")
        db.add(role)
        db.commit()
        db.refresh(role)
        assert role.id is not None
        assert role.name == "admin"
        assert role.display_name == "管理员"

    def test_create_permission(self, db):
        """创建权限"""
        perm = Permission(
            code="detection:task:create",
            name="创建检测任务",
            module="detection",
        )
        db.add(perm)
        db.commit()
        db.refresh(perm)
        assert perm.id is not None
        assert perm.code == "detection:task:create"
        assert perm.module == "detection"

    def test_user_role_association(self, db):
        """用户-角色关联"""
        user = User(username="roleuser", email="role@example.com", hashed_password="hash")
        role = Role(name="operator", display_name="操作员")
        db.add_all([user, role])
        db.flush()

        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.add(user_role)
        db.commit()
        db.refresh(user_role)

        assert user_role.id is not None
        assert user_role.user_id == user.id
        assert user_role.role_id == role.id

    def test_role_permission_association(self, db):
        """角色-权限关联"""
        role = Role(name="operator", display_name="操作员")
        perm = Permission(code="detection:task:read", name="查看检测任务", module="detection")
        db.add_all([role, perm])
        db.flush()

        rp = RolePermission(role_id=role.id, permission_id=perm.id)
        db.add(rp)
        db.commit()
        db.refresh(rp)
        assert rp.id is not None


class TestDetectionModels:
    """检测业务模型测试"""

    def test_create_detection_scene(self, db):
        """创建检测场景"""
        scene = DetectionScene(
            name="remote_sensing",
            display_name="遥感目标检测",
            category="remote_sensing",
            class_names=["airplane", "storage-tank"],
            class_names_cn={"airplane": "飞机", "storage-tank": "储罐"},
        )
        db.add(scene)
        db.commit()
        db.refresh(scene)
        assert scene.id is not None
        assert scene.category == "remote_sensing"
        assert "airplane" in scene.class_names
        assert scene.class_names_cn["airplane"] == "飞机"

    def test_create_detection_task(self, db):
        """创建检测任务"""
        user = User(username="taskuser", email="task@example.com", hashed_password="hash")
        scene = DetectionScene(
            name="test_scene", display_name="测试场景", category="industry",
            class_names=["defect"],
        )
        db.add_all([user, scene])
        db.flush()

        task = DetectionTask(
            user_id=user.id,
            scene_id=scene.id,
            task_type="single",
            conf_threshold=0.5,
            image_size=640,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert task.id is not None
        assert task.status == "pending"
        assert task.task_type == "single"
        assert task.conf_threshold == 0.5

    def test_detection_result(self, db):
        """创建检测结果"""
        user = User(username="resuser", email="res@example.com", hashed_password="hash")
        scene = DetectionScene(
            name="res_scene", display_name="结果场景", category="agriculture",
            class_names=["pest"],
        )
        db.add_all([user, scene])
        db.flush()

        task = DetectionTask(user_id=user.id, scene_id=scene.id, task_type="single")
        db.add(task)
        db.flush()

        result = DetectionResult(
            task_id=task.id,
            image_path="/path/to/image.jpg",
            class_name="pest",
            class_id=0,
            confidence=0.95,
            bbox=[100, 200, 300, 400],
            image_width=800,
            image_height=600,
        )
        db.add(result)
        db.commit()
        db.refresh(result)

        assert result.id is not None
        assert result.class_name == "pest"
        assert result.confidence == 0.95
        assert result.bbox == [100, 200, 300, 400]


class TestTrainingModels:
    """模型训练模型测试"""

    def test_create_training_task(self, db):
        """创建训练任务"""
        user = User(username="trainuser", email="train@example.com", hashed_password="hash")
        model = Model(
            name="测试训练模型",
            base_architecture="yolo26n",
            category="industry",
            class_names=["item"],
        )
        db.add_all([user, model])
        db.flush()

        task = TrainingTask(
            user_id=user.id,
            model_id=model.id,
            task_uuid="uuid-12345",
            base_architecture="yolo26n",
            epochs=100,
            batch_size=16,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert task.id is not None
        assert task.status == "pending"
        assert task.base_architecture == "yolo26n"
        assert task.task_uuid == "uuid-12345"

    def test_training_metric(self, db):
        """创建训练指标"""
        user = User(username="metricuser", email="metric@example.com", hashed_password="hash")
        model = Model(
            name="测试指标模型",
            base_architecture="yolo26s",
            category="traffic",
            class_names=["car"],
        )
        db.add_all([user, model])
        db.flush()

        task = TrainingTask(
            user_id=user.id, model_id=model.id, task_uuid="uuid-metric",
            base_architecture="yolo26s",
        )
        db.add(task)
        db.flush()

        metric = TrainingMetric(
            task_id=task.id,
            epoch=1,
            box_loss=0.5,
            cls_loss=0.3,
            precision=0.85,
            recall=0.78,
            map50=0.82,
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)

        assert metric.id is not None
        assert metric.epoch == 1
        assert metric.map50 == 0.82


class TestChatModels:
    """智能体对话模型测试"""

    def test_create_chat_session(self, db):
        """创建对话会话"""
        user = User(username="chatuser", email="chat@example.com", hashed_password="hash")
        db.add(user)
        db.flush()

        session = ChatSession(
            user_id=user.id,
            session_uuid="session-uuid-001",
            title="测试对话",
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        assert session.id is not None
        assert session.status == "active"
        assert session.title == "测试对话"

    def test_chat_message(self, db):
        """创建对话消息"""
        user = User(username="msguser", email="msg@example.com", hashed_password="hash")
        db.add(user)
        db.flush()

        session = ChatSession(user_id=user.id, session_uuid="session-msg")
        db.add(session)
        db.flush()

        message = ChatMessage(
            session_id=session.id,
            role="user",
            content="请帮我检测这张图片中的目标",
            agent_used="supervisor",
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        assert message.id is not None
        assert message.role == "user"
        assert "检测" in message.content
        assert message.agent_used == "supervisor"


class TestOperationLog:
    """操作日志模型测试"""

    def test_create_operation_log(self, db):
        """创建操作日志"""
        user = User(username="loguser", email="log@example.com", hashed_password="hash")
        db.add(user)
        db.flush()

        log = OperationLog(
            user_id=user.id,
            username=user.username,
            module="auth",
            action="login",
            target_type="user",
            target_id=str(user.id),
            description="用户登录成功",
            ip_address="127.0.0.1",
            request_method="POST",
            request_path="/api/auth/login",
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.id is not None
        assert log.module == "auth"
        assert log.action == "login"
        assert log.status == "success"


class TestCascadeDelete:
    """级联删除测试"""

    def test_delete_user_cascades_roles(self, db):
        """删除用户时级联删除用户角色关联"""
        user = User(username="cascade", email="cascade@example.com", hashed_password="hash")
        role = Role(name="temp_role", display_name="临时角色")
        db.add_all([user, role])
        db.flush()

        user_role = UserRole(user_id=user.id, role_id=role.id)
        db.add(user_role)
        db.commit()

        # 确认关联存在
        assert db.query(UserRole).filter(UserRole.user_id == user.id).count() == 1

        # 删除用户
        db.delete(user)
        db.commit()

        # 关联应被级联删除
        assert db.query(UserRole).filter(UserRole.user_id == user.id).count() == 0

    def test_delete_task_cascades_results(self, db):
        """删除检测任务时级联删除检测结果"""
        user = User(username="taskdel", email="taskdel@example.com", hashed_password="hash")
        scene = DetectionScene(
            name="del_scene", display_name="删除场景", category="industry",
            class_names=["item"],
        )
        db.add_all([user, scene])
        db.flush()

        task = DetectionTask(user_id=user.id, scene_id=scene.id, task_type="single")
        db.add(task)
        db.flush()

        result = DetectionResult(
            task_id=task.id, image_path="/test.jpg",
            class_name="item", class_id=0, confidence=0.9,
            bbox=[0, 0, 100, 100],
        )
        db.add(result)
        db.commit()

        assert db.query(DetectionResult).filter(DetectionResult.task_id == task.id).count() == 1

        db.delete(task)
        db.commit()

        assert db.query(DetectionResult).filter(DetectionResult.task_id == task.id).count() == 0
