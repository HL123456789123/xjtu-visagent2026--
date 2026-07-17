# Food Recognition V1 数据库与模块接线说明

唯一对外契约为仓库根目录的 `api_v1.md`。本说明只记录其在 ORM、Repository 和运行时中的实现，不定义第二套 API 字段。

## 已实现的数据结构

| 实体 | 关键字段 | 用途 |
| --- | --- | --- |
| `food_recognition_tasks` | `id`、`user_id`、`image_object_name`、`status`、`provider`、`model_version`、`raw_detections`、`confirmed_ingredients` | 同步 Food 识别任务和用户最终快照 |
| `recipes` | `id`、`user_id`、`recognition_id`、`version`、`recipe_data`、`generator` | MVP 完整菜谱 JSON 和版本号 |
| `chat_sessions.recipe_id` | 可空外键到 `recipes.id` | 让 V1 Chat Session 关联菜谱 |

唯一新增 migration 是 `b4d91f0c2a7e_add_food_recipe_v1_tables.py`，其 `upgrade` 和 `downgrade` 已在 SQLite 临时库中回归验证。

## Repository 边界

`FoodRepository` 负责：

- `create_recognition(...)`
- `get_recognition_for_user(recognition_id, user_id)`
- `save_raw_detections(recognition_id, detections)`
- `replace_confirmed_ingredients(recognition_id, user_id, ingredients, confirmed_at)`
- `get_confirmed_ingredients(recognition_id, user_id)`

`RecipeRepository` 负责首次创建 `version=1`、按用户读取，以及更新时 `version + 1`。`ChatRepository` 负责按用户创建/读取会话和保存消息。调用方不应直接书写 SQLAlchemy 查询。

## Food 运行时

`POST /api/food/recognitions` 在同一请求中完成：

```text
验证单张 JPG/JPEG/PNG（最大 10 MB）
→ 上传原图到 MinIO
→ 调用 YOLO Provider
→ ModelDetection 转 IngredientCandidate
→ 保存 raw_detections
→ 返回同步识别结果
```

`PUT /api/food/recognitions/{recognition_id}/ingredients` 完整覆盖 `confirmed_ingredients`。所有读取和覆盖都先检查任务存在性和用户归属，跨用户访问返回 403。

`image_url` 对应 `GET /api/files/food/{recognition_id}`；该接口也执行当前用户校验，随后从 MinIO 读取原图。

## Provider 与 Docker

- 食品识别固定使用 `FOOD_PROVIDER=yolo`，严格读取 `FOOD_MODEL_PATH` 和 `FOOD_CLASSES_PATH`；缺权重、类别文件或推理失败均映射为 HTTP 503。
- `docker-compose.yml` 会把宿主机 `./models/food` 以只读方式挂载到容器 `/models/food`。
- Docker 启动前执行 `alembic upgrade head`，再启动 Uvicorn。

权重 `best.pt` 与 `manifest.json` 随仓库交付。权重或类别文件不可用时返回 V1 规定的模型不可用响应，不会降级为虚拟识别结果。
