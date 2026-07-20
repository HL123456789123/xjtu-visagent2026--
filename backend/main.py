from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config.settings import settings
from app.core.rate_limiter import limiter
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.food import file_router as food_file_router
from app.api.food import router as food_router
from app.api.recipes import router as recipes_router
from app.api.dashboard import router as dashboard_router
from app.api.knowledge import router as knowledge_router
from app.api.food_models import router as food_models_router
from app.api.admin import router as admin_router
from app.core.logger import setup_logger
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.middleware.request_logger import RequestLoggerMiddleware


# 初始化日志系统
logger = setup_logger()


def init_minio():
    """初始化 MinIO 存储桶"""
    from app.storage.minio_client import MinIOClient
    try:
        minio_client = MinIOClient()
        logger.info(f"MinIO 存储桶 '{minio_client.bucket_name}' 初始化完成")
    except Exception as e:
        logger.error(f"MinIO 初始化失败: {e}")


def init_redis():
    """初始化 Redis 连接"""
    from app.storage.redis_client import redis_client
    if redis_client.is_connected():
        logger.info("Redis 连接成功")
    else:
        logger.warning("Redis 连接失败，缓存功能将不可用")


def init_seed():
    """初始化固定的三级角色与权限，不创建任何默认账号。"""
    from app.database.session import SessionLocal
    from app.database.seed import seed_scenes

    # 数据库表结构由 Alembic 迁移管理，不再使用 create_all
    # 启动前请确保已执行: alembic upgrade head

    db = SessionLocal()
    try:
        seed_scenes(db)
    except Exception as e:
        logger.error(f"种子数据初始化失败: {e}")
    finally:
        db.close()


def init_food_model_runtime():
    """Restore the active registered model after a backend restart when available."""
    from app.database.session import SessionLocal
    from app.services.food_model_service import FoodModelService

    db = SessionLocal()
    try:
        if FoodModelService(db).initialize_active_runtime():
            logger.info("已恢复数据库中启用的 Food 模型")
    except Exception as exc:
        logger.warning(f"Food 模型注册表尚不可用，继续使用环境配置: {type(exc).__name__}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在初始化服务...")
    _validate_security_config()
    init_minio()
    init_redis()
    init_seed()
    init_food_model_runtime()
    yield
    # 关闭时执行：优雅清理资源
    logger.info("正在关闭服务...")
    await _shutdown_cleanup()
    logger.info("服务已关闭")


def _validate_security_config():
    """校验安全配置，防止使用不安全的默认值"""
    insecure_jwt_values = {"", "your-super-secret-key-change-in-production", "visagent-dev-secret-key-2026"}

    # 1. JWT 密钥校验
    if settings.JWT_SECRET_KEY in insecure_jwt_values or len(settings.JWT_SECRET_KEY) < 32:
        if not settings.DEBUG:
            logger.error(
                "安全错误: JWT_SECRET_KEY 未配置或使用了不安全的默认值，"
                "请在 .env 中配置强密钥（至少 32 字符）！非 DEBUG 模式下拒绝启动。"
            )
            raise SystemExit(1)
        else:
            logger.warning(
                "安全警告: JWT_SECRET_KEY 未配置或使用了不安全的默认值，请在 .env 中配置强密钥！"
            )

    # 2. 数据库/MinIO 默认密码校验（非 DEBUG 模式下拒绝启动）
    insecure_defaults = {
        "DB_PASSWORD": ("visagent", settings.DB_PASSWORD),
        "MINIO_SECRET_KEY": ("minioadmin", settings.MINIO_SECRET_KEY),
    }
    for field_name, (default_val, current_val) in insecure_defaults.items():
        if current_val == default_val:
            if not settings.DEBUG:
                logger.error(
                    f"安全错误: {field_name} 仍为默认值 '{default_val}'，"
                    f"请在 .env 中配置强密码！非 DEBUG 模式下拒绝启动。"
                )
                raise SystemExit(1)
            else:
                logger.warning(
                    f"安全警告: {field_name} 使用了默认值 '{default_val}'，生产环境务必修改！"
                )

    if settings.DEBUG:
        logger.warning("调试模式已开启 (DEBUG=True)，生产环境请务必关闭")


async def _shutdown_cleanup():
    """优雅关闭 LLM 与 Redis 客户端。"""

    # 1. 关闭 LLM httpx 客户端
    try:
        from app.services.llm_gateway import get_llm_gateway

        gateway = get_llm_gateway()
        if gateway.client is not None:
            await gateway.client.close()
            logger.info("LLM httpx 客户端已关闭")
        get_llm_gateway.cache_clear()
    except Exception as e:
        logger.error(f"LLM 客户端关闭失败: {e}")

    # 2. 关闭 Redis 连接
    try:
        from app.storage.redis_client import redis_client

        if hasattr(redis_client, "client") and redis_client.client:
            redis_client.client.close()
            logger.info("Redis 连接已关闭")
    except Exception as e:
        logger.error(f"Redis 关闭失败: {e}")


# 创建 FastAPI 实例
app = FastAPI(
    title="VisAgent",
    version="0.1.0",
    description="食材识别、菜谱生成与智能对话平台 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── API 限流配置 ─────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── 注册异常处理器 ──────────────────────────────────
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# ── 注册中间件 ──────────────────────────────────────
# 请求日志中间件（注意：中间件按注册的逆序执行）
app.add_middleware(RequestLoggerMiddleware)

# CORS 中间件配置
# 允许前端跨域请求后端 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"],
    expose_headers=["X-Request-Id"],
)

# ── 注册路由 ─────────────────────────────────────────
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(food_router)
app.include_router(food_file_router)
app.include_router(recipes_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(knowledge_router)
app.include_router(food_models_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "message": "欢迎使用 VisAgent",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


def startup():
    import uvicorn
    uvicorn.run("main:app", reload=True, host="0.0.0.0", port=8888)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", reload=True, host="0.0.0.0", port=8888)
