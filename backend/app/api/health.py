"""
健康检查 API 路由
- GET /api/health - 应用基础健康检查
- GET /api/health/database - 真实检测 PostgreSQL 连接
- GET /api/health/redis - 真实检测 Redis 连接
- GET /api/health/minio - 真实检测 MinIO 连接
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger("health")

router = APIRouter(prefix="/api/health", tags=["健康检查"])


@router.get("")
async def health_check():
    """应用基础健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/database")
async def database_health():
    """真实检测 PostgreSQL 连接"""
    try:
        from app.database.session import SessionLocal

        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "postgresql",
                "message": "数据库连接正常",
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "postgresql",
                "message": f"数据库连接失败: {str(e)}",
            },
        )


@router.get("/redis")
async def redis_health():
    """真实检测 Redis 连接"""
    from app.storage.redis_client import redis_client

    if redis_client.is_connected():
        return {
            "status": "healthy",
            "redis": "connected",
            "message": "Redis 连接正常",
        }
    else:
        logger.error("Redis 健康检查失败: 连接不可用")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "redis": "disconnected",
                "message": "Redis 连接失败",
            },
        )


@router.get("/minio")
async def minio_health():
    """真实检测 MinIO 连接"""
    try:
        from minio import Minio

        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        # 尝试列出存储桶来验证连接
        client.list_buckets()
        return {
            "status": "healthy",
            "minio": "connected",
            "message": "MinIO 连接正常",
        }
    except Exception as e:
        logger.error(f"MinIO 健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "minio": "disconnected",
                "message": f"MinIO 连接失败: {str(e)}",
            },
        )
