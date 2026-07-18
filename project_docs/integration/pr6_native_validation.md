# PR #8 原生环境验收记录

- 验证日期：2026-07-18
- 执行人：闫灿宇（项目经理 / 集成负责人）
- 验证分支：`fix/pr6-docker-env`
- 验证 Commit：`7a164f36c2e0bffce182c0b05e329bbfb7af19e0`
- 集成基线：`origin/integration/rebuild-v1.1`，已包含 PR #7、#9、#10；本次同步基线为 `ddddda256aaa6cc8cc2fd3de1de51ffbf853ce7f`。
- 运行模式：`FOOD_PROVIDER=mock`、`LLM_MODE=fake`；仅使用本地忽略的 `backend/.env`，未读取、记录或提交其中的敏感值。

## 环境与工具

| 项目 | 实际结果 |
| --- | --- |
| 操作系统 | Windows 11 专业版，10.0.26100 |
| Python | 3.11.15 |
| uv | 0.11.26 |
| Bun / Node | 1.3.14 / v24.16.0 |
| PostgreSQL | 15.18 |
| Redis | 8.8.0；项目客户端使用 RESP2，兼容 Redis 5/7/8 的普通命令语义 |
| MinIO | `RELEASE.2025-09-07T16-13-09Z` |

## 依赖、迁移和后端检查

从 `backend/` 执行：

- `uv lock --check`：通过。
- `uv sync --locked --group dev`：通过；锁定依赖未发生变更。
- `uv run ruff check app/`：通过。
- `uv run alembic heads`：只有一个 head，`a7e1c9f42d6b`。
- `uv run alembic upgrade head`：通过。
- 使用本地忽略 `.env` 注入测试子进程后运行完整 pytest：收集 164 项，`164 passed`、`0 failed`、`0 errors`、`0 skipped`。

后端仅有 1 条第三方 `FastAPI TestClient` 弃用警告，不影响测试结果。

## 前端检查

从 `frontend/` 执行：

- `bun install --frozen-lockfile`：通过，未改动锁文件。
- `bun run test`：12 个测试文件、`107 passed`。
- `bun run build`：通过。
- 本地页面验证：FridgeChef 登录页实际呈现，包含 FridgeChef 品牌、登录表单和注册入口。
- 未生成 `package-lock.json`。

构建输出包含 `@vueuse/core` PURE 注释及大于 500 kB chunk 的提示；构建退出成功。这是前端优化跟踪项，不是本次原生门禁失败。

## Food V1.1 与异常边界

在真实本地 PostgreSQL、Redis、MinIO 上，以授权用户调用 API 验证：

| 场景 | 实际结果 |
| --- | --- |
| 缺少 `images` | `400 / INVALID_IMAGE_COUNT` |
| 空 multipart | `400 / INVALID_IMAGE_COUNT` |
| 1 张图片 | 成功 |
| 5 张图片 | 成功 |
| 6 张图片 | `400 / INVALID_IMAGE_COUNT` |
| 旧公开字段 `image` | `400 / INVALID_IMAGE_COUNT` |
| 单张超过 10 MiB | `413 / IMAGE_TOO_LARGE` |
| Real Food 且权重不存在 | `503 / FOOD_MODEL_UNAVAILABLE` |
| Real LLM 且 Key 为空 | `503 / LLM_UNAVAILABLE` |

Food API 继续只接受公开 multipart 字段 `images`；未发现旧字段恢复。

## Mock/Fake 全链路

实际完成：

1. 使用 FridgeChef 认证接口登录；
2. 上传 2 张图片，并返回 `image_index` 为 `0`、`1`；
3. Mock Food 空候选后人工确认食材；
4. 创建 Recipe，初始 `version=1` 并包含营养免责声明；
5. 创建 Chat 并发送“改成三人份并少放油”；
6. SSE 按顺序收到 `token`、`recipe_updated`、`done`，没有旧事件；
7. 再次查询 Recipe，确认版本更新为 `version=2`。

## Docker 门禁

本记录是原生环境验收。`docker compose config`、`docker compose build`、`docker compose up -d`、容器健康检查及容器内全链路验证**尚未执行**，不得据此宣称 Docker 发布门禁已通过。

真实 YOLO 推理成功和真实 LLM 成功调用也未执行：本次只验证了缺失权重或 Key 时按 V1.1 返回正确的 503 错误。

## 结论

PR #8 已同步 PR #9、#10 的集成基线，原生运行门禁通过。PR #8 继续保持 Draft；Docker 门禁、真实 YOLO 权重验证和真实 LLM 授权验证仍是后续发布条件。
