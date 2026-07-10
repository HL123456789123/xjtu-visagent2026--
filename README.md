# VisAgent - 视觉目标检测智能体平台

基于 YOLOv11 的视觉目标检测智能体平台，集成 AI 对话、图像/视频检测、模型训练、知识库管理等功能，提供一站式 AI 检测服务。

## 技术栈

| 层级       | 技术                                           |
| ---------- | ---------------------------------------------- |
| 后端框架   | FastAPI + Uvicorn                              |
| AI 编排    | LangChain + LangGraph（多 Agent 协作）          |
| 目标检测   | Ultralytics YOLOv11 + PyTorch 2.2.2            |
| 前端框架   | Vue 3 + Vite + Element Plus + ECharts          |
| 数据库     | PostgreSQL（pgvector 向量扩展）                 |
| 缓存       | Redis                                          |
| 对象存储   | MinIO                                          |
| 包管理     | uv（Python）/ bun（Node.js）                    |
| 容器化     | Docker Compose                                 |
| 大模型     | OpenAI 兼容接口（支持 GPT-4o 等）              |

## 快速开始

### 1. 环境要求

- Python 3.11+（推荐 3.12）
- Node.js 18+（推荐使用 bun）
- Docker & Docker Compose
- PostgreSQL 15+（可通过 Docker 启动）

### 2. 启动基础服务

```bash
docker compose up -d
```

启动 PostgreSQL（含 pgvector）、Redis、MinIO。

### 3. 配置并启动后端

```bash
cd backend

# 复制并编辑环境变量
cp .env.example .env
# 必须填写：OPENAI_API_KEY（大模型API密钥）
# 必须填写：JWT_SECRET_KEY（JWT加密密钥）

# 安装依赖
uv sync

# 启动开发服务器
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888
```

**后端服务地址**：
- API 服务：`http://localhost:8888`
- API 文档：`http://localhost:8888/docs`
- 健康检查：`http://localhost:8888/api/health`

### 4. 配置并启动前端

```bash
cd frontend

# 安装依赖
bun install

# 启动开发服务器
bun run dev
```

**前端服务地址**：
- 开发服务器：`http://localhost:3000`
- Vite 自动将 `/api` 代理到后端 `8888` 端口

## 项目结构

```
visagent/
├── docker-compose.yml          # 全栈服务编排（PG + Redis + MinIO + 前后端）
├── backend/
│   ├── app/
│   │   ├── api/                # API 路由层（10 个模块，72 个端点）
│   │   │   ├── auth.py         # 认证（注册/登录/登出/当前用户/刷新Token）
│   │   │   ├── camera.py       # 摄像头场景管理
│   │   │   ├── chat.py         # 对话会话管理
│   │   │   ├── dashboard.py    # 数据看板
│   │   │   ├── detection.py    # 目标检测（单张/批量/文件夹/视频）
│   │   │   ├── health.py       # 健康检查
│   │   │   ├── knowledge.py    # 知识库（上传/检索/删除）
│   │   │   ├── model.py        # 模型管理（模型/版本/场景绑定）
│   │   │   ├── training.py     # 模型训练 + 数据集转换 + 模型管理
│   │   │   └── admin.py        # 管理后台（用户/角色/权限管理）
│   │   ├── config/             # 全局配置（pydantic-settings）
│   │   ├── core/               # 核心工具（安全/JWT/日志/异常）
│   │   ├── database/           # 数据库（会话/种子数据）
│   │   ├── entity/             # 数据实体（ORM 模型 + Pydantic Schema）
│   │   ├── middleware/         # 中间件（请求日志）
│   │   ├── services/           # 业务服务层（9 个模块）
│   │   │   ├── agent_graph.py    # LangGraph 多 Agent 编排
│   │   │   ├── agent_prompts.py  # Agent 系统提示词
│   │   │   ├── agent_tools.py    # Agent 工具集（检测/查询/知识库）
│   │   │   ├── chat_service.py   # 对话服务
│   │   │   ├── data_utils.py     # 数据处理工具
│   │   │   ├── detection_service.py  # 检测服务
│   │   │   ├── knowledge_service.py  # 知识库服务
│   │   │   ├── training_service.py   # 训练服务
│   │   │   └── user_service.py       # 用户服务
│   │   └── storage/            # 外部存储（MinIO + Redis）
│   ├── alembic/                # 数据库迁移
│   ├── tests/                  # 测试套件
│   ├── main.py                 # 应用入口
│   ├── Dockerfile              # 后端容器构建
│   └── pyproject.toml
└── frontend/
    ├── src/
    │   ├── api/                 # API 请求封装（auth/chat/detection/training/history）
    │   ├── assets/styles/       # SCSS 样式系统（变量/重置/全局）
    │   ├── components/layout/   # 布局组件（Header/Sidebar/MainLayout）
    │   ├── router/              # Vue Router（路由守卫 + 权限控制）
    │   ├── stores/              # Pinia 状态管理（user/agent）
    │   ├── utils/               # 工具函数
    │   │   ├── errorReporter.js   # 全局错误监控上报
    │   │   ├── markdown.js        # Markdown 渲染
    │   │   ├── request.js         # Axios 封装（拦截器/Token）
    │   │   └── stream.js          # SSE 流式响应处理
    │   └── views/               # 页面视图（12 个页面）
    │       ├── ChatPage.vue       # 智能对话（多 Agent 协作）
    │       ├── DashboardPage.vue  # 数据看板（ECharts 图表）
    │       ├── DetectionPage.vue  # 目标检测（图片/视频/摄像头）
    │       ├── HistoryPage.vue    # 检测历史记录
    │       ├── TrainingPage.vue   # 模型训练管理
    │       ├── LoginPage.vue      # 登录
    │       ├── RegisterPage.vue   # 注册
    │       ├── ProfilePage.vue    # 个人中心
    │       ├── UserManagePage.vue # 用户管理
    │       ├── RoleManagePage.vue # 角色管理
    │       ├── ModelPage.vue      # 模型管理
    │       └── NotFoundPage.vue   # 404 页面
    ├── Dockerfile              # 前端容器构建（Nginx）
    ├── nginx.conf              # Nginx 反向代理配置
    └── package.json
```

## 功能特性

### AI 智能对话

- 基于 LangGraph 的多 Agent 协作架构（Supervisor + Detection + Analysis + QA）
- 支持 SSE 流式响应，实时输出对话内容
- Agent 工具集：目标检测触发、历史记录查询、统计分析、知识库检索

### 目标检测

- 基于 YOLOv11，支持单张图片、批量图片、文件夹、视频四种检测模式
- 摄像头实时检测（WebSocket 推流）
- 检测场景管理（场景配置、置信度阈值、IoU 阈值）
- 检测结果可视化（边界框标注、类别统计）

### 模型训练

- 训练任务全生命周期管理（创建/启动/暂停/取消/恢复）
- 数据集格式转换：VOC → YOLO / COCO → YOLO / LabelMe → YOLO
- 训练指标实时监控（loss、mAP、precision、recall）
- 模型版本管理与下载
- 数据集验证与自动划分
- 支持 macOS Intel CPU 训练（PyTorch 2.2.2）

### 知识库管理

- 文档上传与向量化存储（pgvector）
- 语义检索，支持在对话中引用知识库内容
- 知识库统计与文档管理

### 用户与权限

- JWT 认证（注册/登录/登出）
- RBAC 权限模型（用户 → 角色 → 权限）
- 个人中心（信息查看与修改）
- 管理后台（用户管理、角色管理）

### 系统运维

- 操作审计日志
- 全局错误监控与上报
- 数据看板（ECharts 可视化）
- 健康检查（数据库/Redis/MinIO）

## 数据库模型（16 张表）

| 业务域     | 表名               | 说明           |
| ---------- | ------------------ | -------------- |
| 用户权限   | `users`            | 用户表         |
|            | `roles`            | 角色表         |
|            | `permissions`      | 权限表         |
|            | `user_roles`       | 用户-角色关联  |
|            | `role_permissions` | 角色-权限关联  |
| 检测业务   | `detection_scenes` | 检测场景配置   |
|            | `detection_tasks`  | 检测任务记录   |
|            | `detection_results`| 检测结果明细   |
| 模型体系   | `models`           | 模型表         |
|            | `model_versions`   | 模型版本       |
|            | `scene_models`     | 场景-模型关联  |
|            | `training_tasks`   | 训练任务       |
|            | `training_metrics` | 训练指标       |
| 智能体对话 | `chat_sessions`    | 对话会话       |
|            | `chat_messages`    | 对话消息       |
| 系统运维   | `operation_logs`   | 操作审计日志   |

## API 端点（72 个）

| 模块     | 端点数 | 主要功能                                  |
| -------- | ------ | ----------------------------------------- |
| 认证     | 4      | 注册、登录、登出、获取当前用户            |
| 对话     | 5      | 会话 CRUD、消息发送（SSE 流式）           |
| 检测     | 9      | 单张/批量/文件夹/视频检测、任务管理、场景管理 |
| 训练     | 17     | 任务生命周期、数据集转换、模型管理        |
| 知识库   | 4      | 文档上传、语义检索、统计、删除            |
| 模型     | 13     | 模型管理、版本管理、场景绑定              |
| 摄像头   | 1      | 摄像头场景列表                            |
| 看板     | 2      | 平台统计、用户统计                        |
| 健康检查 | 4      | 服务状态、数据库、Redis、MinIO            |
| 管理后台 | 13     | 用户管理、角色管理、权限管理              |

## 开发指南

### 后端开发

```bash
cd backend

# 代码检查
uv run ruff check app/

# 代码格式化
uv run ruff format app/

# 运行测试
uv run pytest
```

### 前端开发

```bash
cd frontend

# 代码检查
bun run lint

# 运行测试
bun run test

# 构建生产版本
bun run build

# 预览生产构建
bun run preview
```

### 容器化部署

```bash
docker compose up -d
```

## 依赖版本说明

### 后端核心依赖

| 依赖包 | 版本要求 | 说明 |
|--------|----------|------|
| FastAPI | >=0.139.0 | Web 框架 |
| Uvicorn | >=0.49.0 | ASGI 服务器 |
| SQLAlchemy | >=2.0.50 | ORM |
| LangChain | >=1.3.0 | AI 编排框架 |
| LangGraph | >=1.2.0 | 多 Agent 协作 |
| OpenAI | >=2.44.0 | 大模型调用 |
| Ultralytics | >=8.4.0 | YOLOv11 检测 |
| PyTorch | ==2.2.2 | 深度学习框架（macOS Intel 优化） |
| pgvector | >=0.4.0 | 向量存储扩展 |

### 前端核心依赖

| 依赖包 | 版本要求 | 说明 |
|--------|----------|------|
| Vue | 3.x | 前端框架 |
| Pinia | >=3.0.4 | 状态管理 |
| Element Plus | >=2.14.2 | UI 组件库 |
| Axios | >=1.18.1 | HTTP 客户端 |
| ECharts | >=6.1.0 | 图表可视化 |
| Vite | >=8.1.3 | 构建工具 |
| Vitest | >=3.2.1 | 测试框架 |

## 环境变量配置

### 后端配置 (`backend/.env`)

```bash
cd backend
cp .env.example .env
```

**必需配置**：
- `OPENAI_API_KEY` - OpenAI API 密钥（或其他兼容接口）
- `JWT_SECRET_KEY` - JWT 认证密钥

**可选配置**：
- `DB_*` - 数据库连接信息（默认与 docker-compose 一致）
- `REDIS_*` - Redis 连接信息
- `MINIO_*` - MinIO 对象存储配置
- `LANGCHAIN_*` - LangChain 监控配置（可选）

详细配置参见 [backend/.env.example](backend/.env.example)

### 前端配置 (`frontend/.env`)

```bash
cd frontend
cp .env.example .env
```

**主要配置**：
- `VITE_API_BASE_URL` - API 基础地址（默认 `http://localhost:8888`）
- `VITE_APP_TITLE` - 应用标题
- `VITE_MINIO_URL` - MinIO 访问地址

详细配置参见 [frontend/.env.example](frontend/.env.example)

## 许可证

本项目采用 [木兰宽松许可证 v2](http://license.coscl.org.cn/MulanPSL2)。
