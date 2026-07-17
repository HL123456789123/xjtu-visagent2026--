# 吴雯 Day2 测试报告与 Docker 阻断清单

## 今日目标

- 按 V1 固定契约补强 Food、Recipe、Chat SSE 契约测试。
- 检查 Docker Compose、PostgreSQL、Redis、MinIO、Nginx 配置。
- 只在本人负责文件内提交测试、fixture 使用、Docker 编排与日志记录；不直接修改业务 owner 文件。

## 开始前读取

- 已读取 `docs/contracts/api_v1_多图支持修订版.md` 全文。当前工作树中 `docs/contracts/api_v1.md` 不存在，且处于已删除状态。
- 《10-日志监控与单元测试.pdf》《11-Docker容器化部署.pdf》未在当前仓库或工作区可读文件中找到，无法直接摘录；本日按 V1、现有测试和 Docker 文件执行。

## 已完成改动

- `backend/tests/test_food_contract.py`
  - 保留 `food_recognition_success.json` 和 `food_recognition_empty.json` fixture 校验。
  - 新增 V1 三条 Food API 静态契约检查：`POST /api/food/recognitions`、`GET /api/food/recognitions/{recognition_id}`、`PUT /api/food/recognitions/{recognition_id}/ingredients`。
  - 新增登录、`current_user` 隔离和 main 路由注册检查。
- `backend/tests/test_recipe_contract.py`
  - 保留 `recipe_success.json` fixture 校验。
  - 新增 V1 两条 Recipe API 静态契约检查：`POST /api/recipes`、`GET /api/recipes/{recipe_id}`。
  - 新增 `recognition_id`、`preferences`、`NO_CONFIRMED_INGREDIENTS`、登录和用户隔离检查。
- `backend/tests/test_chat_sse_contract.py`
  - 保留 `sse_recipe_update.txt` fixture 校验。
  - 新增 Chat 会话 `recipe_id` 绑定、消息 `content` 字段、`text/event-stream`、四类 SSE 命名事件和用户隔离检查。
- `docker-compose.yml`
  - 保留 PostgreSQL、Redis、MinIO，并补充 backend、frontend 服务。
  - PostgreSQL healthcheck 改为跟随 `DB_USER`、`DB_NAME`。
  - backend 接入 postgres、redis、minio 服务名环境变量，并挂载 `./models/food:/models/food:ro`。
  - frontend 暴露 `8080:80`，反向代理到 backend 服务。
- `frontend/nginx.conf`
  - `/api/` 代理改为适合 SSE 的 HTTP 长连接配置。
  - 关闭 proxy buffering/cache，增加 `proxy_read_timeout`、`proxy_send_timeout` 和 `X-Accel-Buffering`。

## 实际命令与结果

### 后端契约测试

命令：

```powershell
cd backend
$env:JWT_SECRET_KEY='test-secret-key-for-contract-tests-123456'
$env:DEBUG='true'
uv run pytest tests/test_food_contract.py tests/test_recipe_contract.py tests/test_chat_sse_contract.py
```

结果：

- 收集 15 项。
- 4 项通过：四个 canonical fixture 结构符合 V1。
- 11 项失败，均为现有业务代码未接入 V1 的契约阻断。

失败摘要：

- `backend/app/api/food.py` 缺失，三条 Food API 无法验证。
- `backend/main.py` 未注册 V1 food router。
- `backend/app/api/recipes.py` 缺失，两条 Recipe API 无法验证。
- `backend/main.py` 未注册 V1 recipes router。
- `backend/app/api/chat.py` 和 `backend/app/entity/schemas.py` 未体现 `recipe_id` 会话绑定。
- Chat 发送消息仍使用旧字段 `message`，V1 要求 `content`。
- Chat SSE 仍不是 `event: token|recipe_updated|done|error` 命名事件格式，且服务中仍含旧 `tool_call/tool_result` 语义。
- `chat_sessions` ORM 尚未绑定 `recipe_id`。

### 前端测试

命令：

```powershell
cd frontend
bun run test
```

结果：

```text
$ vitest run
bun: command not found: vitest
error: script "test" exited with code 1
```

补充检查：

```powershell
Test-Path node_modules
Test-Path node_modules\.bin\vitest.cmd
Test-Path node_modules\.bin\vitest
```

结果均为 `False`。当前环境未安装前端依赖，未进入测试执行阶段。

### Docker Compose 检查

命令：

```powershell
docker compose config
```

结果：

```text
docker : 无法将“docker”项识别为 cmdlet、函数、脚本文件或可运行程序的名称。
```

补充检查：

```powershell
Get-Command docker -ErrorAction SilentlyContinue
Get-Command docker-compose -ErrorAction SilentlyContinue
```

结果均无输出。当前环境 Docker CLI 不在 PATH，无法执行 Compose 解析或服务启动验证。

## Docker 阻断清单

| 编号 | 阻断 | 影响 | 建议 owner |
| --- | --- | --- | --- |
| D2-Docker-01 | 当前环境找不到 `docker` 和 `docker-compose` 命令 | 无法执行 `docker compose config`、无法启动 PostgreSQL/Redis/MinIO/backend/frontend 联调 | 环境负责人 |
| D2-Docker-02 | Compose 需要 `JWT_SECRET_KEY`、`DB_PASSWORD`、`MINIO_SECRET_KEY` 注入 | 不能裸跑生产/联调配置；这是安全要求，不建议写死弱密钥 | 环境负责人 |
| D2-Docker-03 | V1 Food 模型环境变量尚未被后端 settings 接收 | 即使挂载 `/models/food`，当前后端仍没有 Food Provider 配置入口 | 绕家辉 |
| D2-Docker-04 | `backend/app/api/food.py`、`backend/app/api/recipes.py` 缺失 | Docker 环境启动后也无法通过 V1 主流程 | 绕家辉、陈煜君、闫灿宇 |

## 缺陷清单

| 编号 | V1 章节 | 实际差异 | 建议 owner |
| --- | --- | --- | --- |
| D2-API-01 | 五、Food API | 缺少 `backend/app/api/food.py` 及三条 V1 Food 路由 | 绕家辉 |
| D2-API-02 | 十二、固定文件命名 | `backend/main.py` 未注册 food router | 闫灿宇 |
| D2-API-03 | 六、Recipe API | 缺少 `backend/app/api/recipes.py` 及两条 V1 Recipe 路由 | 陈煜君 |
| D2-API-04 | 十二、固定文件命名 | `backend/main.py` 未注册 recipes router | 闫灿宇 |
| D2-API-05 | 八、Chat API 与 SSE | 创建会话请求未按 V1 使用 `recipe_id`，响应也不是 `201 + session_id/recipe_id/created_at` | 陈煜君、李晨宁 |
| D2-API-06 | 八、Chat API 与 SSE | 发送消息请求仍是 `message`，V1 要求 `content` | 陈煜君、李晨宁 |
| D2-API-07 | 八、Chat API 与 SSE | SSE 输出仍是 `data: {"type": ...}` 旧格式，未使用四类命名事件 | 陈煜君 |
| D2-API-08 | 十、数据库决定 | `chat_sessions` 未增加 `recipe_id` | 绕家辉 |
| D2-Test-01 | 测试环境 | `uv run pytest` 首次在沙箱内因 uv 全局缓存目录权限失败，提权后可运行 | 环境负责人 |
| D2-Test-02 | 测试环境 | 前端缺少 `node_modules`/`vitest`，`bun run test` 未进入测试执行阶段 | 前端/环境负责人 |

## 截图记录

本轮验证均为终端命令，当前环境未提供可截图的 Docker/浏览器页面。命令、错误文本和通过/失败数量已在上方完整记录。

## 交付结论

- 本人负责的 canonical fixture 与契约测试已扩展到 Day2 要求的 Food 三条、Recipe 两条、Chat 两条和 SSE 四事件。
- Docker 编排与 Nginx SSE 配置已补齐到可联调结构，但本机缺少 Docker CLI，无法完成实际 `compose config` 和容器启动验证。
- 业务契约仍未通过，原因集中在 V1 Food、Recipe、Chat、ORM 和 main 路由注册缺口；按任务要求交由对应 owner 修复，不在本分支私自修改对外字段或 owner 文件。
