# 项目唯一命令标准

本文件是食物识别菜谱平台团队成员、Codex 和 Qoder 的统一开发命令标准。接口、请求响应、模型输出、Recipe JSON、SSE 和错误码以 `docs/contracts/api_v1.md` 为唯一标准；命令以当前仓库真实配置为准。

除非本文件明确说明，命令不得在错误目录执行，不得换用另一套包管理器，也不得把“配置存在”写成“命令已经运行通过”。

## 1. 工作目录规则

| 工作目录 | 允许执行的命令 |
| --- | --- |
| 仓库根目录 | `git` 检查、`docker compose`、跨模块文档检查 |
| `backend/` | `uv sync`、`uv add`、`uv run uvicorn`、`uv run pytest`、`uv run ruff`、`uv run alembic` |
| `frontend/` | `bun install`、`bun add`、`bun run dev/test/build/preview` |

- 后端命令先进入 `backend/`。
- 前端命令先进入 `frontend/`。
- Docker Compose 命令只从包含 `docker-compose.yml` 的仓库根目录执行。
- 文档中的命令如果没有注明目录，不得直接照抄；先按本节确定工作目录。

## 2. 环境与包管理器

### 后端

- 项目依赖文件：`backend/pyproject.toml`。
- 包管理器：只使用 `uv`。
- Python 约束：`backend/pyproject.toml` 只明确声明 `Python >= 3.11`；当前没有 `.python-version`，也没有可确认的上限。
- 后端 Dockerfile 使用 Python 3.11，但这不等于本地项目声明了唯一 Python 小版本。
- 开发依赖位于 `pyproject.toml` 的 `dev` dependency group。
- 当前 `backend/uv.lock` 不存在，并被 `.gitignore` 排除，但 `backend/Dockerfile` 又要求复制该文件。这是尚未解决的构建阻断，不能声称后端 Docker 构建已可复现。

### 前端

- 项目依赖文件：`frontend/package.json`。
- 包管理器：只使用 `bun`。
- 实际锁文件：`frontend/bun.lock`，已被 Git 跟踪；`bun.lockb` 不存在。
- `package.json` 未声明 Bun 或 Node 的本地版本范围；只能确认前端 Docker 构建阶段当前使用 Node 20。
- 仓库中没有 npm、pnpm 或 yarn 锁文件。

### 统一限制

- 团队和 Agent 不使用 `pip`、`npm`、`pnpm`、`yarn` 管理项目依赖。
- 现有 Dockerfile 使用 `pip`/`npm` 安装 `uv`/`bun` 本身，这是已发现的镜像引导实现，不是团队依赖命令标准；是否改为官方镜像或其他安装方式由吴雯复核。
- 只有确实修改依赖时才允许更新对应依赖文件和锁文件。
- 不得为了“修环境”删除锁文件后重新生成；确需重建必须先得到项目经理明确批准。
- 不得手工编辑锁文件。

## 3. 首次安装

以下命令由项目配置确认存在，但本次审计没有执行依赖安装。

### 后端：从 `backend/` 执行

```bash
cd backend
uv sync --group dev
```

注意：当前缺少 `backend/uv.lock`，首次执行可能生成锁文件。生成后的处理方式、是否取消忽略并纳入 Git，必须由绕家辉、吴雯和项目经理确认，不得私自删除或反复重建。

### 前端：从 `frontend/` 执行

```bash
cd frontend
bun install --frozen-lockfile
```

依赖变更必须使用：

```bash
# backend/ 目录
uv add <package>
uv add --dev <package>

# frontend/ 目录
bun add <package>
bun add -d <package>
```

## 4. 本地启动

### 后端：从 `backend/` 执行，端口 8888

```bash
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8888
```

- 服务地址：`http://localhost:8888`。
- API 文档：`http://localhost:8888/docs`。
- `pyproject.toml` 当前没有 `backend-server` 项目脚本，因此不得使用 `uv run backend-server`。

### 前端：从 `frontend/` 执行，端口 3000

```bash
cd frontend
bun run dev
```

- Vite 固定监听 `http://localhost:3000`。
- `/api` 由 Vite 代理到 `http://localhost:8888`。
- 生产构建的本地预览脚本为 `bun run preview`；它不是开发启动命令。

## 5. 测试与构建

### 后端：从 `backend/` 执行

```bash
cd backend
uv run ruff check app/
uv run pytest
```

- 测试目录实际为 `backend/tests/`。
- 当前没有 `pytest.ini`，`pyproject.toml` 中也没有 `[tool.pytest]` 配置；测试发现依赖 pytest 默认规则。

### 前端：从 `frontend/` 执行

```bash
cd frontend
bun run test
bun run build
```

- `test`、`test:watch`、`dev`、`build`、`preview` 均真实存在于 `package.json`。
- 当前不存在 `lint` script，不得使用或声称已运行 `bun run lint`；需要由前端 owner 决定是否补充。

### Docker 配置检查：从仓库根目录执行

```bash
docker compose config
```

当前审计机器没有可用的 Docker CLI，因此本次未能实际通过该检查。不得把静态读取 Compose 文件写成 `docker compose config` 已通过。

## 6. 数据库迁移

Alembic 配置实际位于 `backend/alembic.ini`，迁移目录为 `backend/alembic/`，`env.py` 从后端 settings 读取数据库 URL。以下命令只从 `backend/` 执行：

```bash
cd backend
uv run alembic current
uv run alembic upgrade head
```

- 执行前必须确认目标是允许操作的本地或测试数据库。
- 创建或修改 migration 只允许数据库 owner 绕家辉执行。
- Agent 不得自动执行 `alembic revision`，不得创建第二条 migration 链，也不得私改 `backend/alembic/versions/`。
- 本次审计没有连接数据库，也没有运行 `current` 或 `upgrade head`。

## 7. Docker 命令

Compose 文件实际服务名只有：`postgres`、`redis`、`minio`、`backend`、`frontend`。

以下命令从仓库根目录执行：

```bash
# 校验配置
docker compose config

# 构建应用镜像
docker compose build backend frontend

# 启动全部服务
docker compose up -d

# 查看状态
docker compose ps

# 查看应用日志
docker compose logs -f backend frontend

# 停止并移除 Compose 容器和网络；不删除命名卷
docker compose down
```

- 前端宿主机端口为 3000，容器端口为 80。
- 后端宿主机和容器端口均为 8888。
- 基础设施端口来自当前 Compose：PostgreSQL 5432、Redis 6379、MinIO 9000/9001。
- 当前 `backend/uv.lock` 缺失而 Dockerfile 要求复制它，修复前 `docker compose build backend` 不能被视为可通过。
- 本机 Docker CLI 当前不可用，以上命令为项目统一标准，不是本次已通过结果。

## 8. 环境变量规则

- 真实环境文件只允许放在 `backend/.env`、`frontend/.env` 等本地路径，不进入 Git。
- 根目录当前没有 `.env.example`；后端示例为 `backend/.env.example`，前端示例为 `frontend/.env.example`。
- 新增或修改环境变量时，必须在同一 PR 同步对应 `.env.example`，示例中只放占位符或安全默认值。
- 不得读取、打印、记录或提交 API Key、Token、密码和真实 `.env` 内容。
- `best.pt`、其他模型权重和大型数据集不进入 Git，只能通过本地路径、挂载或受控存储交付。
- 现有后端配置主要使用 `OPENAI_*`；V1 为 Food/LLM Mock 与真实模式冻结了 `FOOD_*` 和 `LLM_*` 名称。相关模块接入时必须以 `docs/contracts/api_v1.md` 为准，并同步 settings 与 `backend/.env.example`，不得再创造别名。
- 当前 settings 和 `backend/.env.example` 尚未完整包含 V1 的 `FOOD_*`/`LLM_*`，对应 owner 未修复前不得声称真实/Mock 模式环境已经配置完成。

## 9. PR 前最低检查

提交 PR 时使用 `project_docs/integration/pr_environment_checklist.md` 记录实际工作目录、实际命令、真实结果、未运行项及原因。以下项目按改动范围执行，不能运行时必须如实登记。

### 只要修改后端代码

从 `backend/` 执行：

```bash
uv run ruff check app/
uv run pytest
```

### 只要修改前端代码

从 `frontend/` 执行：

```bash
bun run test
bun run build
```

### 修改 Dockerfile 或 `docker-compose.yml`

从仓库根目录执行：

```bash
docker compose config
docker compose build backend frontend
```

只构建实际受影响的应用服务也可以，但服务名必须来自本文件第 7 节。无法运行 Docker 时必须在 PR 中明确写“未运行”及原因。

### 修改数据库或 migration

从 `backend/` 对允许操作的本地/测试数据库执行：

```bash
uv run alembic current
uv run alembic upgrade head
uv run pytest
```

### 只修改文档

从仓库根目录对本次目标文件执行：

```bash
git diff --check -- <本次文档路径>
git diff -- <本次文档路径>
```

只审查实际目标文件，不得用全仓格式化或全量暂存代替检查。

## 10. Agent 执行限制

- 开始前先读取根目录 `AGENTS.md` 和 `docs/contracts/api_v1.md`。
- 已有代码先审计再修改；对外契约冲突优先建议 Adapter，不维护第二套公开接口。
- 不执行 `git add .`、`git add -A` 或 `git commit -am`；只能精确暂存本次目标文件。
- 不执行 `git reset --hard`、`git clean`、rebase 或 force push。
- 不擅自切换包管理器，不使用 pip/npm/pnpm/yarn 修改项目依赖。
- 不删除或手工改写锁文件，不因安装失败私自重建环境。
- 不修改、输出或提交真实 `.env`、密钥、Token、模型权重和大型数据集。
- 不声称未运行的测试、构建、迁移或 Docker 检查已经通过。
- 完成后必须列出修改文件、实际执行命令、实际结果、未运行项和风险。
- Commit、Push、PR、Approve、Merge 默认由成员确认后执行；只有用户在当前任务明确授权时才可执行。

## 11. 提交约定

- 使用 Conventional Commits。
- 冒号后的标题和提交说明使用中文。
- 按功能或模块分类提交，不把无关工作区差异带入 Commit。

示例：

```text
feat(food): 实现食材确认接口
feat(agent): 实现菜谱修改流程
fix(stream): 修复SSE分块解析
test(contract): 增加统一契约测试
docs(env): 统一开发命令
chore(docker): 修复容器构建
```

## 12. 当前已知环境缺口与复核 Owner

| 问题 | 当前证据 | 复核 Owner |
| --- | --- | --- |
| 后端锁文件缺失 | `backend/uv.lock` 不存在且被忽略，但后端 Dockerfile 执行 `COPY pyproject.toml uv.lock ./` | 吴雯主责，绕家辉复核，闫灿宇裁决 |
| Docker 无法本机验证 | 当前机器找不到 Docker CLI，`docker compose config` 未运行成功 | 吴雯 |
| Dockerfile 引导工具混用 | 后端镜像用 pip 安装 uv，前端镜像用 npm 安装 bun；应用依赖后续仍由 uv/bun 管理 | 吴雯 |
| Food 模式变量未接入现有配置 | V1 的 `FOOD_*` 尚未完整出现在 settings 和后端 `.env.example` | 黄小石、绕家辉 |
| LLM 模式变量未接入现有配置 | V1 的 `LLM_*` 尚未完整出现在 settings 和后端 `.env.example` | 陈煜君 |
| 前端命令复核 | `package.json` 没有 `lint` script，但 README 仍推荐 `bun run lint`；Bun 版本也未在项目中固定 | 刘楚涵、李晨宁 |
| 命令标准维护 | `AGENTS.md` 与计划、README、课程讲义或旧提示出现冲突时需要统一裁决 | 闫灿宇 |
| 运行时版本未完全固定 | Python 仅声明 `>=3.11`，未声明上限；项目未固定本地 Bun/Node 版本 | 绕家辉、前端 owner、闫灿宇 |
