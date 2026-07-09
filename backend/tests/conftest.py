"""
测试配置文件
- 使用 PostgreSQL 测试数据库（visagent_test）
- 提供 FastAPI TestClient 和数据库会话 fixture
"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# ── 测试数据库配置 ──────────────────────────────────
# 使用独立的测试数据库 visagent_test，避免污染生产数据
TEST_DB_NAME = "visagent_test"
TEST_DB_USER = os.getenv("DB_USER", "visagent")
TEST_DB_PASSWORD = os.getenv("DB_PASSWORD", "visagent")
TEST_DB_HOST = os.getenv("DB_HOST", "localhost")
TEST_DB_PORT = os.getenv("DB_PORT", "5432")

TEST_DATABASE_URL = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"

# ── 在导入应用模块之前，设置测试环境变量 ──
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from app.database.session import Base
from main import app


# ── 测试数据库引擎 ────────────────────────────────
test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def ensure_test_database():
    """确保测试数据库存在，如果不存在则创建"""
    # 连接到默认的 postgres 数据库来创建测试数据库
    default_url = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/postgres"
    default_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
    
    with default_engine.connect() as conn:
        # 检查测试数据库是否存在
        result = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": TEST_DB_NAME}
        )
        if not result.fetchone():
            # 创建测试数据库
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
            print(f"已创建测试数据库: {TEST_DB_NAME}")
    
    default_engine.dispose()


# 启动时确保测试数据库存在
try:
    ensure_test_database()
except Exception as e:
    print(f"警告: 无法创建测试数据库 {TEST_DB_NAME}: {e}")
    print("请确保 PostgreSQL 正在运行，并且用户有创建数据库的权限")


@pytest.fixture(scope="function")
def db():
    """每个测试函数独立的数据库会话"""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient"""
    with TestClient(app) as c:
        yield c
"""
测试配置文件
- 使用 SQLite 内存数据库替代 PostgreSQL
- 提供 FastAPI TestClient 和数据库会话 fixture
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# ── 在导入应用模块之前，设置测试环境变量 ──
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.database.session import Base
from main import app


# ── 测试数据库引擎 ────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    """每个测试函数独立的数据库会话"""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient"""
    with TestClient(app) as c:
        yield c
