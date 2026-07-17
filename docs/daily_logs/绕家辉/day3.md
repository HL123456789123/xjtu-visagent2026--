# Day 3：Mock 全链路与用户隔离

> 补录日期：2026-07-15。

## 完成内容

- 使用 `FOOD_PROVIDER=mock` 形成可运行的同步识别链路。
- 识别结果由 `ModelDetection` 转换为含 `candidate_id`、中文 `display_name` 的 `IngredientCandidate`。
- raw detections 与 confirmed ingredients 都持久化为 JSON。
- 确认接口使用完整 `ingredients` 数组覆盖旧快照。
- 读取、确认、原图读取全部核验当前用户；跨用户访问返回 HTTP 403。
- `RecipeRepository.create_recipe()` 固定创建 `version=1`，`save_new_recipe_version()` 固定递增版本。

## 本人检查

- Food 专项测试使用真实 SQLite ORM Repository，不使用进程内字典伪造持久化。
- API 测试覆盖创建、查询、原图读取、确认覆盖和跨用户 403。

## 结果与风险

- Mock API 及 Repository 回归均通过。
- PostgreSQL、MinIO 的容器 E2E 需要 Docker daemon；当前本机 Docker daemon 未启动。
