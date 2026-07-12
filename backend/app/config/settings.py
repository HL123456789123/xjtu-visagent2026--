"""
全局配置模块
使用 pydantic-settings 管理所有配置项，支持从 .env 文件和环境变量读取
加载优先级：环境变量（系统级别）> .env 文件 > 代码中的默认值
"""

from pydantic_settings import BaseSettings
from pydantic import model_validator, field_validator
import warnings


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
        """获取实际数据库连接字符串（支持 DATABASE_URL 环境变量覆盖）"""
        if self.DATABASE_URL:
            # 验证不使用 SQLite
            if "sqlite" in self.DATABASE_URL.lower():
                raise ValueError(
                    "禁止使用 SQLite 数据库！项目仅支持 PostgreSQL。"
                    "请配置 PostgreSQL 连接字符串，例如: postgresql://user:pass@localhost:5432/dbname"
                )
            return self.DATABASE_URL
        # 构造 PostgreSQL 连接字符串
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── Redis 配置 ────────────────────────────────────
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def redis_url(self) -> str:
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
    ALLOWED_DETECTION_DIRS: str = "/tmp"
    """允许文件夹检测访问的目录白名单，逗号分隔（生产环境请通过 .env 配置）"""

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

    @field_validator('DB_PORT')
    @classmethod
    def validate_db_port(cls, v: int) -> int:
        """验证数据库端口范围"""
        if not (1 <= v <= 65535):
            raise ValueError('数据库端口必须在 1-65535 之间')
        return v

    @field_validator('REDIS_PORT')
    @classmethod
    def validate_redis_port(cls, v: int) -> int:
        """验证 Redis 端口范围"""
        if not (1 <= v <= 65535):
            raise ValueError('Redis 端口必须在 1-65535 之间')
        return v

    @field_validator('ACCESS_TOKEN_EXPIRE_MINUTES')
    @classmethod
    def validate_token_expire(cls, v: int) -> int:
        """验证 Token 过期时间"""
        if v < 1:
            raise ValueError('Token 过期时间必须大于 0 分钟')
        if v > 1440:  # 24 小时
            warnings.warn('Token 过期时间超过 24 小时，可能存在安全风险', UserWarning)
        return v

    @field_validator('OPENAI_BASE_URL')
    @classmethod
    def validate_openai_url(cls, v: str) -> str:
        """验证 OpenAI API URL 格式"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('OpenAI API URL 必须以 http:// 或 https:// 开头')
        return v

    @field_validator('MAX_CACHED_MODELS')
    @classmethod
    def validate_max_cached_models(cls, v: int) -> int:
        """验证模型缓存数量"""
        if v < 1:
            raise ValueError('模型缓存数量必须大于 0')
        if v > 20:
            warnings.warn('模型缓存数量超过 20，可能导致内存占用过高', UserWarning)
        return v

    @model_validator(mode='after')
    def check_security_critical(self) -> 'Settings':
        """启动前校验关键安全配置，缺失则阻止启动"""
        # JWT_SECRET_KEY 不能为空
        if not self.JWT_SECRET_KEY:
            raise ValueError(
                "JWT_SECRET_KEY 未配置！请在 .env 文件中设置 JWT_SECRET_KEY，"
                "例如: JWT_SECRET_KEY=your-strong-random-secret-key"
            )
        return self

    @model_validator(mode='after')
    def check_default_passwords(self) -> 'Settings':
        """检测并警告使用默认密码的风险"""
        default_passwords = {
            'DB_PASSWORD': ('visagent', self.DB_PASSWORD),
            'MINIO_SECRET_KEY': ('minioadmin', self.MINIO_SECRET_KEY),
        }
        
        warnings_list = []
        for field, (default, current) in default_passwords.items():
            if current == default:
                warnings_list.append(f"{field} 使用了默认值 '{default}'，这会导致安全风险！")
        
        if warnings_list:
            warning_msg = "\n⚠️ 安全警告：" + "\n".join(warnings_list)
            warning_msg += "\n请在 .env 文件中设置强密码，生产环境务必修改默认密码。"
            warnings.warn(warning_msg, UserWarning, stacklevel=2)
        
        return self


# 创建全局单例，其他模块直接 import 使用
settings = Settings()
