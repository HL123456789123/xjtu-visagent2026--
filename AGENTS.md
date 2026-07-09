# Agent 指南



## 数据库

后端项目中必须使用 PostgreSQL 数据库，绝对禁止使用 SQLite 数据库。



### 后端开发命令（使用 `uv`）

```bash
cd backend

# 安装依赖（含开发依赖）
uv sync --group dev

# 添加依赖
uv add <package>

# 添加开发依赖
uv add --dev <package>

# 运行开发服务器（需先配置 .env）
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888

# 或使用项目脚本
uv run backend-server

# 代码检查
uv run ruff check app/

# 代码格式化
uv run ruff format app/

# 运行测试
uv run pytest

# 激活虚拟环境
source .venv/bin/activate
```

> **注意**：后端要求 Python 3.11 到 3.14 之间，推荐使用 `.python-version` 中指定的版本。

### 配置

- `.env.example` → 复制为 `.env`，填写实际值
- 关键配置项：`OPENAI_API_KEY`（必需）、`SECRET_KEY`（必需）、`DATABASE_URL`、`DEVICE`

---





### 前端开发命令（使用 `bun`）

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

---

## 运行完整应用

### 1. 启动后端

```bash
cd backend

# 确保 .env 已配置（至少需要 OPENAI_API_KEY 和 SECRET_KEY）
cp .env.example .env
# 编辑 .env 填入实际值

# 安装依赖并启动
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888
```

后端默认运行在 `http://localhost:8888`，API 文档在 `http://localhost:8888/docs`。

### 2. 启动前端

```bash
cd frontend

bun install
bun run dev
```

前端默认运行在 `http://localhost:3000`，Vite 自动将 `/api` 请求代理到后端。

### 3. 首次启动自动完成

- 数据库自动创建（SQLite `data/visagent.db`）
- 若 `INIT_DEFAULT_ADMIN=true`，自动创建默认管理员（账号/密码见 `init_admin.py`）

---



## 约定式提交

1. 采用Git“约定式提交”将本次操作涉及的所有文件全部提交到本地仓库
2. 提交时使用的描述信息(注释)必须使用汉字，不要使用英文，格式举例如下：

```
feat(task_manager): 新增训练任务中断恢复与checkpoint清理逻辑

- 新增 _recover_interrupted_tasks() 方法，启动时自动处理因进程重启中断的任务

	- 有 checkpoint 的 running/paused 任务标记为 paused 等待手动恢复

	- 无 checkpoint 的 running 任务标记为 failed

- 新增 _clean_resume_checkpoint() 方法，任务完成/删除时清理恢复用 checkpoint

- 修改训练启动逻辑，存在 checkpoint 时自动加载续训

- 修改 delete_task 流程，删除时附带清理 checkpoint
```

3. 不要一次性提交所有文件，要分类或分模块或者按功能作用来分类提交
