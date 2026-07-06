"""
全局配置模块
使用 pydantic-settings 管理所有配置项，支持从 .env 文件和环境变量读取
加载优先级：环境变量（系统级别）> .env 文件 > 代码中的默认值
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用全局配置"""

    # ── 应用基础配置 ──────────────────────────────────
    APP_NAME: str = "VisAgent"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
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
    JWT_SECRET_KEY: str = ""  # 必须通过环境变量或 .env 配置
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── 大模型配置 ────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    # ── LangChain 配置 ────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "visagent"

    # ── 安全配置 ────────────────────────────────────────
    ALLOWED_DETECTION_DIRS: str = "/tmp,/data,/home"
    """允许文件夹检测访问的目录白名单，逗号分隔"""

    ALLOWED_TRAINING_DIRS: str = "/tmp,/data,/home"
    """允许训练任务访问的目录白名单，逗号分隔"""

    MAX_CACHED_MODELS: int = 5
    """检测服务模型 LRU 缓存最大数量"""

    COOKIE_SECURE: bool = True
    """Cookie 安全标志，生产环境需开启 HTTPS"""

    # ── CORS 配置 ────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173,http://localhost:8080"

    @property
    def cors_origins_list(self) -> list:
        """将 CORS 配置字符串转为列表"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 创建全局单例，其他模块直接 import 使用
settings = Settings()
