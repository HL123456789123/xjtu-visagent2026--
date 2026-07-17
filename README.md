# VisAgent

基于 YOLO26 的目标检测智能体平台，集成了大语言模型（LLM）能力，提供数据集管理、模型训练、模型管理和目标检测等核心功能。

## 核心功能

- **数据集管理**：数据集注册、目录浏览、自动发现、完整性校验
- **模型训练**：YOLO26 训练任务管理、中断恢复、设备探测、逐 Epoch 指标记录
- **模型管理**：Model + ModelVersion 两层架构、版本管理、启用/禁用、场景关联
- **目标检测**：单图、批量、视频、实时摄像头四种检测模式
- **AI Agent**：基于 LangGraph 的智能体工作流，支持自然语言交互

## 技术栈

### 后端

- **运行时**：Python 3.11+
- **Web 框架**：FastAPI
- **数据库**：PostgreSQL + pgvector
- **缓存**：Redis
- **对象存储**：MinIO
- **AI 框架**：LangChain + LangGraph
- **目标检测**：Ultralytics (YOLO26) + PyTorch
- **依赖管理**：uv

### 前端

- **框架**：Vue 3 + Vite
- **UI 组件**：Element Plus
- **状态管理**：Pinia
- **图表**：ECharts
- **HTTP 客户端**：Axios
- **包管理**：bun

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- Python 3.11+（本地开发）
- Node.js 18+（本地开发）
- bun（前端包管理器）
- uv（后端包管理器）

### 1. 启动基础设施服务

```bash
# 使用 backend/.env 配置启动 PostgreSQL、Redis、MinIO
docker compose --env-file backend/.env up -d
```

服务端口：
- PostgreSQL：5432
- Redis：6379
- MinIO API：9000
- MinIO 控制台：9001

### 2. 配置后端

```bash
cd backend

# 复制环境变量配置
cp .env.example .env

# 编辑 .env，填入实际配置
# 至少需要配置：
# - OPENAI_API_KEY（大模型 API 密钥）
# - DB_PASSWORD（数据库密码）
# - MINIO_SECRET_KEY（MinIO 密钥）

# 安装依赖
uv sync

# 启动开发服务器
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888
```

后端默认运行在 `http://localhost:8888`，API 文档在 `http://localhost:8888/docs`。

### 3. 配置前端

```bash
cd frontend

# 安装依赖
bun install

# 启动开发服务器
bun run dev
```

前端默认运行在 `http://localhost:3000`，自动代理 `/api` 请求到后端。

### Docker 代理网络下构建

前端镜像默认通过 `https://registry.npmmirror.com` 安装依赖，并在下载包校验失败时清理缓存后重试。通常直接执行即可：

```bash
docker compose build frontend
```

如果当前网络更适合 npm 官方源，可以临时覆盖 Registry；代理不稳定时还可以继续降低并发数：

```bash
BUN_REGISTRY=https://registry.npmjs.org BUN_NETWORK_CONCURRENCY=8 docker compose build frontend
```

PowerShell 对应写法：

```powershell
$env:BUN_REGISTRY = "https://registry.npmjs.org"
$env:BUN_NETWORK_CONCURRENCY = "8"
docker compose build frontend
```

## 开发指南

### 后端开发

```bash
cd backend

# 安装依赖（含开发依赖）
uv sync --group dev

# 添加依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 代码检查
uv run ruff check app/

# 代码格式化
uv run ruff format app/

# 运行测试
uv run pytest

# 激活虚拟环境
source .venv/bin/activate
```

### 前端开发

```bash
cd frontend

# 安装依赖
bun install

# 添加依赖
bun add <package>

# 添加开发依赖
bun add -d <package>

# 启动开发服务器（端口 3000，自动代理 /api → http://localhost:8888）
bun run dev

# 构建生产版本
bun run build

# 预览生产构建
bun run preview
```

## 项目结构

```
visagent/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/               # API 路由
│   │   ├── config/            # 配置
│   │   ├── core/              # 核心工具
│   │   ├── database/          # 数据库
│   │   ├── entity/            # 数据模型
│   │   ├── middleware/        # 中间件
│   │   ├── services/          # 业务逻辑
│   │   └── storage/           # 存储客户端
│   ├── alembic/               # 数据库迁移
│   ├── tests/                 # 测试
│   ├── .env                   # 环境变量
│   └── pyproject.toml         # Python 项目配置
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── api/               # API 调用
│   │   ├── components/        # 组件
│   │   ├── router/            # 路由
│   │   ├── stores/            # 状态管理
│   │   ├── utils/             # 工具函数
│   │   └── views/             # 页面视图
│   └── package.json           # Node.js 项目配置
├── docker-compose.yml          # Docker Compose 配置
└── AGENTS.md                   # AI Agent 开发指南
```

## 默认管理员账号

系统启动时会幂等创建默认普通管理员。公开注册或由管理员新增的账号只能成为普通用户。普通管理员可以升级普通用户，但不能降级、禁用或删除其他管理员；只有 `super_admin` 身份可以执行这些管理员级操作。

| 用户名 | 密码 | 邮箱 | 角色 |
|--------|------|------|------|
| admin | admin2026 | admin@visagent.com | 管理员 |

管理端“系统管理”包含：

- 用户管理：新增、搜索、编辑、启停和删除用户。
- 角色管理：按用户名或邮箱搜索用户，并在普通用户与管理员之间调整身份。

## 许可证

MIT License

---

**注意**：本项目数据库仅支持 PostgreSQL，禁止使用 SQLite。
