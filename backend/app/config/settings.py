"""
全局配置模块
使用 pydantic-settings 管理所有配置项，支持从 .env 文件和环境变量读取
加载优先级：环境变量（系统级别）> .env 文件 > 代码中的默认值
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # ── 应用基础配置 ──────────────────────────────────
    APP_NAME: str = "VisAgent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ── 数据库配置 ────────────────────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "visagent"
    DB_USER: str = "visagent"
    DB_PASSWORD: str = "visagent"

    DATABASE_URL: str = ""

    @property
    def database_url(self) -> str:
        """获取实际数据库连接字符串（支持 DATABASE_URL 环境变量覆盖，方便测试用 SQLite）"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        """构造 PostgreSQL 连接字符串"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── Redis 配置 ────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def REDIS_URL(self) -> str:
        """构造 Redis 连接字符串"""
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # ── MinIO 配置 ────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "visagent-images"
    MINIO_SECURE: bool = False

    # ── JWT 认证配置 ──────────────────────────────────
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── 大模型配置 ────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    # ── 食物识别配置（V1） ───────────────────────────────
    FOOD_PROVIDER: Literal["mock", "yolo"] = "mock"
    FOOD_MODEL_PATH: str = "models/food/best.pt"
    FOOD_CLASSES_PATH: str = "scripts/food_model/classes.yaml"
    FOOD_CONF_THRESHOLD: float = 0.25
    FOOD_MODEL_VERSION: str = "food-yolo-v1"

    # ── LangChain 配置 ────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "visagent"

    # ── CORS 配置 ────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list:
        """将 CORS 配置字符串转为列表"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, value):
        """兼容本地开发环境中常见的 ``release`` 配置写法。"""
        if isinstance(value, str) and value.strip().lower() in {"release", "production"}:
            return False
        return value

    @field_validator("FOOD_CONF_THRESHOLD")
    @classmethod
    def validate_food_conf_threshold(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("FOOD_CONF_THRESHOLD 必须位于 0 到 1 之间")
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 创建全局单例，其他模块直接 import 使用
settings = Settings()
