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

# ── 测试环境禁用速率限制 ────────────────────────────
from app.core.rate_limiter import limiter
import pytest as _pytest

@_pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """每个测试前重置限流器存储，避免触发限流"""
    try:
        limiter._storage.reset()
    except Exception:
        pass


# ── RBAC 种子数据 fixture ─────────────────────────
@pytest.fixture(scope="function")
def seed_rbac(db):
    """创建默认角色和权限，供测试使用"""
    from app.entity.db_models import Role, Permission, UserRole, RolePermission
    from app.database.seed import (
        DEFAULT_ROLES, DEFAULT_PERMISSIONS, ROLE_PERMISSIONS_MAP,
    )

    # 创建权限
    perm_map = {}
    for p in DEFAULT_PERMISSIONS:
        perm = Permission(code=p["code"], name=p["name"], module=p["module"])
        db.add(perm)
        perm_map[p["code"]] = perm
    db.flush()

    # 创建角色并分配权限
    role_map = {}
    for r in DEFAULT_ROLES:
        role = Role(
            name=r["name"],
            display_name=r["display_name"],
            description=r["description"],
            is_system=r["is_system"],
        )
        db.add(role)
        db.flush()
        role_map[r["name"]] = role

        # 分配权限
        for perm_code in ROLE_PERMISSIONS_MAP.get(r["name"], []):
            if perm_code in perm_map:
                rp = RolePermission(role_id=role.id, permission_id=perm_map[perm_code].id)
                db.add(rp)
    db.commit()
    return role_map


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
