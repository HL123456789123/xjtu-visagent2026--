"""
健康检查 & 根路由 API 测试
"""

from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestRoot:
    """根路由测试"""

    def test_root_returns_welcome(self):
        """GET / 返回欢迎信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "欢迎使用 VisAgent"
        assert data["version"] == "0.1.0"
        assert "/docs" in data["docs"]
        assert "/redoc" in data["redoc"]


class TestHealth:
    """健康检查端点测试"""

    def test_health_check(self):
        """GET /api/health 返回健康状态"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app_name"] == "VisAgent"
        assert data["version"] == "0.1.0"

    def test_database_health(self):
        """GET /api/health/database 返回数据库状态"""
        response = client.get("/api/health/database")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "数据库连接正常" in data["message"]

    def test_redis_health(self):
        """GET /api/health/redis 真实反映 Redis 在线或离线状态。"""
        response = client.get("/api/health/redis")
        assert response.status_code in {200, 503}
        data = response.json()
        if response.status_code == 200:
            assert data["status"] == "healthy"
            assert "Redis 连接正常" in data["message"]
        else:
            assert data == {"code": 503, "message": "Redis 连接失败", "data": None}

    def test_minio_health(self):
        """GET /api/health/minio 真实反映 MinIO 在线或离线状态。"""
        response = client.get("/api/health/minio")
        assert response.status_code in {200, 503}
        data = response.json()
        if response.status_code == 200:
            assert data["status"] == "healthy"
            assert "MinIO 连接正常" in data["message"]
        else:
            assert data["code"] == 503
            assert "MinIO 连接失败" in data["message"]
            assert data["data"] is None


class TestDocs:
    """API 文档端点测试"""

    def test_swagger_docs(self):
        """GET /docs 可访问"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_docs(self):
        """GET /redoc 可访问"""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_schema(self):
        """GET /openapi.json 返回 OpenAPI Schema"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "VisAgent"
        assert "/api/auth/register" in data["paths"]
        assert "/api/auth/login" in data["paths"]
        assert "/api/auth/me" in data["paths"]
