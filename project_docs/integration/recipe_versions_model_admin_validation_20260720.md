# Recipe 版本与模型管理开发验证记录

日期：2026-07-20
分支：`codex/recipe-versions-model-admin`
代码基线：`2ff1393ef7dc16b012ec1dca7b5299331523c1df`

## 结论

菜谱不可变版本、对话上下文恢复、三级角色、用户管理、Food 模型注册与安全切换、用户端精简和分享弹窗已经完成代码与自动化验证。单链 Alembic migration 已通过独立数据库的升级、降级、再升级验证，正式本地数据库已升级，新版 Docker 已运行。

运行配置确认为 `FOOD_PROVIDER=yolo`、`LLM_MODE=real`，LLM Key 仅确认已配置且未显示。本轮部署后只执行了不调用 LLM 的只读和权限冒烟，因此仍不得把它写成完整 Real LLM 业务验收或最终发布通过。

## 修改前备份

- 备份目录：`D:\bytecreek\backups\visagent\20260720-103320`
- Git bundle SHA-256：`7B053ABE6183BD4CF32553C0B9FCFB15E8507794DFE8DAE2E5BBA498FEE8BF02`
- PostgreSQL 逻辑备份 SHA-256：`7BBD3802719B8371D9B9B5730C46B1B280A9C554C34EA654216B4C06F1E514C4`
- 备份未包含 `.env`、API Key、Token、模型权重或训练集。

正式迁移前再次备份到 `D:\bytecreek\backups\visagent\20260720-124538-premigration`：

- Git bundle SHA-256：`BE4FFCB6A24C662E404F6210677302AD02B6B4F17B21BE4CC6D4980E38FE3307`
- PostgreSQL 逻辑备份 SHA-256：`76857402593183DF9C0B0F31E9D9A5F488EC346B2A30E636546A3D8A72209E8B`

## 自动化验证

| 项目 | 命令/环境 | 结果 |
| --- | --- | --- |
| 后端静态检查 | `backend/`：`uv run ruff check app/` | 通过 |
| 后端全量测试 | Docker 临时容器，独立 `visagent_test` | `197 passed`，1 个第三方弃用警告 |
| 前端全量测试 | `frontend/`：`bun run test -- --run` | `124 passed` |
| 前端生产构建 | `frontend/`：`bun run build` | 通过 |
| Compose 配置 | `docker compose -p visagent-history-dev config --quiet` | 通过 |
| 应用镜像构建 | `docker compose -p visagent-history-dev build backend frontend` | 通过，约 15 秒 |
| Alembic | `heads` / `current` | 均为单一 `5d14fc303d6d (head)` |
| Migration 往返 | 独立数据库 `upgrade -> downgrade -> upgrade` | 通过，最终为 `5d14fc303d6d (head)` |
| 正式本地库 | `alembic upgrade head` | 通过，`5d14fc303d6d (head)` |
| 部署后 API | 注册、登录、模型状态、历史空态、管理员 API | 通过，普通用户管理员 API 为 403 |

构建警告仅包括第三方 VueUse pure annotation 和前端大分包提示。测试中的 Element Plus 未注册组件提示来自浅挂载环境，不影响测试结果或生产构建。

## 覆盖范围

- 初次生成、结构化对话更新和恢复旧版本分别创建不可变菜谱快照。
- 普通对话不增加版本；SSE 保留 `token -> recipe_updated -> done`。
- 菜谱、版本、会话和消息均按当前用户隔离，跨用户读取被拒绝。
- 对话恢复当前菜谱、摘要和最近 12 条消息；摘要失败不打断已保存回复。
- 固定 `super_admin`、`admin`、`user` 权限规则，阻止自提权和越权管理。
- 旧检测、训练、数据集、摄像头、角色和旧模型公开 API 已下线为 404，旧表与历史数据保留。
- 模型 ZIP 覆盖 Hash、类别、任务不匹配、路径穿越、压缩炸弹、冒烟失败回滚和活跃模型删除拒绝。
- detect 保留多目标 bbox；classify 返回整图 ROI，并标记 `task=classify`、`localization=full_image`。
- 前端覆盖精简文案、分享弹窗、版本时间线、刷新恢复、权限导航、用户管理和模型状态。

## 人工界面检查

- 已检查普通用户桌面与 390px 移动视口，页面宽度无横向溢出。
- 已检查模型管理和用户管理管理员页面。
- 视觉检查使用的随机临时管理员及其审计日志已删除，未记录密码。
- 当前五服务均保持运行，backend/frontend 已切换为新版镜像，没有删除命名卷。

## 待复验项

1. 用标准模型 ZIP 验证上传、冒烟、启用、回滚、删除和重启持久化。
2. 完成一次 YOLO Detect/Real LLM 菜谱生成与结构化对话更新业务链路。
3. 新分类权重交付后，验证单图 Top-1 和整图分类提示。

## Git 与敏感信息

只提交源码、测试、契约和本验证文档。本地 `.env`、API Key、`best.pt`、训练集、前端日志及 PPT 检查产物均不纳入 Git。
