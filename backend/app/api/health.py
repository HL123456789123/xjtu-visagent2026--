"""
健康检查 API 路由
- GET /api/health - 应用基础健康检查
- GET /api/health/database - 真实检测 PostgreSQL 连接
- GET /api/health/redis - 真实检测 Redis 连接
- GET /api/health/minio - 真实检测 MinIO 连接
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.logger import get_logger
from app.database.session import get_db

logger = get_logger("health")

router = APIRouter(prefix="/api/health", tags=["健康检查"])


@router.get("")
async def health_check():
    """应用基础健康检查"""
    return {
        "status": "ok",
    }


@router.get("/database")
async def database_health(db: Session = Depends(get_db)):
    """真实检测 PostgreSQL 连接"""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
            },
        )


@router.get("/redis")
async def redis_health():
    """真实检测 Redis 连接"""
    from app.storage.redis_client import redis_client

    if redis_client.is_connected():
        return {
            "status": "ok",
        }
    else:
        logger.error("Redis 健康检查失败: 连接不可用")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
            },
        )


@router.get("/minio")
async def minio_health():
    """真实检测 MinIO 连接"""
    try:
        from app.storage.minio_client import get_minio_client

        client = get_minio_client()
        # 尝试列出存储桶来验证连接
        client.client.list_buckets()
        return {
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"MinIO 健康检查失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "degraded",
            },
        )
