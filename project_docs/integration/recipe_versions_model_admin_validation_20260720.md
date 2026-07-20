# Recipe 版本与模型管理开发验证记录

日期：2026-07-20
分支：`codex/recipe-versions-model-admin`
代码基线：`2ff1393ef7dc16b012ec1dca7b5299331523c1df`

## 结论

菜谱不可变版本、对话上下文恢复、三级角色、用户管理、Food 模型注册与安全切换、用户端精简和分享弹窗已经完成代码与自动化验证。Compose 配置和应用镜像构建通过。

数据库 owner 尚未生成新结构的单链 Alembic migration，因此没有重建当前业务后端，也没有宣称新版 Docker 业务链路或最终发布通过。完成 migration 后必须再执行 Mock/Fake、YOLO Detect/Real LLM、分类模型、热切换和重启持久化复验。

## 修改前备份

- 备份目录：`D:\bytecreek\backups\visagent\20260720-103320`
- Git bundle SHA-256：`7B053ABE6183BD4CF32553C0B9FCFB15E8507794DFE8DAE2E5BBA498FEE8BF02`
- PostgreSQL 逻辑备份 SHA-256：`7BBD3802719B8371D9B9B5730C46B1B280A9C554C34EA654216B4C06F1E514C4`
- 备份未包含 `.env`、API Key、Token、模型权重或训练集。

## 自动化验证

| 项目 | 命令/环境 | 结果 |
| --- | --- | --- |
| 后端静态检查 | `backend/`：`uv run ruff check app/` | 通过 |
| 后端全量测试 | Docker 临时容器，独立 `visagent_test` | `197 passed`，1 个第三方弃用警告 |
| 前端全量测试 | `frontend/`：`bun run test -- --run` | `124 passed` |
| 前端生产构建 | `frontend/`：`bun run build` | 通过 |
| Compose 配置 | `docker compose -p visagent-history-dev config --quiet` | 通过 |
| 应用镜像构建 | `docker compose -p visagent-history-dev build backend frontend` | 通过，约 15 秒 |
| Alembic | `heads` / `current` | 均为单一 `a7e1c9f42d6b (head)` |

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
- 当前五服务仍保持运行，没有停止服务或删除命名卷。

## 待复验项

1. 数据库 owner 按交接文档创建并复核单链 migration。
2. 在允许操作的数据库执行 `upgrade head`，确认新增表、列、约束和部分唯一索引。
3. 用标准模型 ZIP 验证上传、冒烟、启用、回滚、删除和重启持久化。
4. 完成 Mock/Fake 与 YOLO Detect/Real LLM 两轮业务链路。
5. 新分类权重交付后，验证单图 Top-1 和整图分类提示。

## Git 与敏感信息

只提交源码、测试、契约和本验证文档。本地 `.env`、API Key、`best.pt`、训练集、前端日志及 PPT 检查产物均不纳入 Git。
