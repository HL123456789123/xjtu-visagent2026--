# Day 2：Food API、ORM 与唯一 Migration

> 补录日期：2026-07-15。

## 完成内容

- 实现并注册三条 V1 Food 路由：
  - `POST /api/food/recognitions`
  - `GET /api/food/recognitions/{recognition_id}`
  - `PUT /api/food/recognitions/{recognition_id}/ingredients`
- 实现受认证保护的 `GET /api/files/food/{recognition_id}`，使 V1 `image_url` 可实际读取原图。
- 新增 `food_recognition_tasks`、`recipes` ORM，新增 `chat_sessions.recipe_id`。
- 新增唯一 Food/Recipe migration：`b4d91f0c2a7e_add_food_recipe_v1_tables.py`。
- 实现 JPG/JPEG/PNG、文件头与 10 MB 限制，分别映射 415、413。

## 本人检查

- 识别任务原图先上传 MinIO，再进行模型识别和数据库持久化。
- 数据库写入失败时补偿删除刚上传的对象。
- 新 migration 在 SQLite 临时库已升级到 head 并成功降级一层。

## 结果与风险

- 数据层和 API 单元测试通过。
- Docker 数据库验证需要 Docker daemon 运行后执行，见 Day 5。
