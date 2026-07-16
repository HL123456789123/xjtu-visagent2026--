# 后端 Dockerfile
# 基于 Python 3.11 slim 镜像

FROM python:3.11-slim-bookworm

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv 包管理器
RUN pip install --no-cache-dir uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 配置国内 PyPI 镜像（解决容器内下载超时）
ENV UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

# 安装 Python 依赖
RUN uv sync --no-dev --no-install-project

# 运行阶段直接使用构建时已同步的虚拟环境，避免容器启动时再次构建项目。
ENV PATH="/app/.venv/bin:${PATH}"

# 复制运行时必需的后端文件。
#
# - app：FastAPI 应用及业务代码
# - alembic / alembic.ini：容器启动时执行数据库迁移
# - scripts：包含 Food Provider 所需的类别文件
# - main.py：Uvicorn 启动入口
#
# 不复制本地 .env、测试数据、虚拟环境与缓存，运行配置统一由容器环境变量提供。
COPY app ./app
COPY alembic ./alembic
COPY scripts ./scripts
COPY alembic.ini main.py ./

# 创建数据目录
RUN mkdir -p data/models data/visagent.db logs

# 暴露端口
EXPOSE 8888

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/health || exit 1

# 启动命令：先执行唯一 Alembic 链，再启动应用，避免依赖 create_all 绕过迁移。
# exec 让 Uvicorn 成为主进程并正确接收 Docker 的停止信号。
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8888"]
