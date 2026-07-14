# 食物识别模块数据库与路由接线说明

## 范围与边界

每次上传一张 JPG 或 PNG 图片，仅创建一条食物识别任务。YOLO 原始结果写入
`raw_detections`；用户调用确认接口后，以请求体中的完整列表覆盖
`confirmed_ingredients`。菜谱模块必须通过 `recognition_id` 关联任务，且只能读取
已确认任务的 `confirmed_ingredients`，不得直接读取原始 YOLO 结果。

Day 1 的 `InMemoryFoodRecognitionRepository` 仅用于让 API 骨架和单元测试可运行。
接入 ORM 后，应实现 `FoodRecognitionRepository` 的 `create`、`get`、`update` 三个异步
方法后注入 `FoodRecognitionService`；不要修改 DTO 字段，也不要增加 Mock/YOLO 模式切换。

## 建议表：`food_recognition_tasks`

| 字段 | 建议类型 | 约束/说明 |
| --- | --- | --- |
| `id` | UUID 或 `varchar(36)` | 主键，对应 API 的 `recognition_id` |
| `user_id` | integer | 非空，外键关联 `users.id` |
| `image_object_name` | varchar(500) | 非空，只保存 MinIO 对象名，不保存本地临时路径 |
| `image_mime_type` | varchar(100) | 非空，`image/jpeg` 或 `image/png` |
| `image_size` | bigint | 非空，原图字节数 |
| `provider` | varchar(20) | 非空，固定保存 `yolo` |
| `model_version` | varchar(100) | 非空，YOLO Provider 版本 |
| `conf_threshold` | float | 非空，范围为 0～1 |
| `status` | varchar(30) | 非空，Day 1 使用 `recognized`、`confirmed` |
| `raw_detections` | JSON | 非空，`IngredientCandidate` 列表 |
| `confirmed_ingredients` | JSON | 非空，初始可为 `[]`，确认后为非空 `ConfirmedIngredient` 列表 |
| `error_message` | text | 可空，为后续失败状态保留 |
| `confirmed_at` | datetime | 可空，确认时写入 |
| `created_at` | datetime | 非空 |
| `updated_at` | datetime | 非空，确认快照覆盖时更新 |

建议创建以下索引：`user_id`、`status`、`created_at`；若查询以“当前用户的创建时间倒序”为主，
可额外建立联合索引 `(user_id, created_at)`。

Repository 的 `get` 与 `update` 应将 `user_id` 一并取回，由 Service 返回 403（任务存在但
不属于当前用户）或 404（任务不存在）。实际 ORM 更新需要在同一事务内完整替换
`confirmed_ingredients`、`status`、`confirmed_at` 和 `updated_at`。

## 路由接线（由入口维护者执行）

本次严格未修改 `backend/main.py`。入口维护者完成依赖接线后，在现有路由导入区增加：

```python
from app.api.food import router as food_router
```

并在其余 `include_router` 调用旁增加：

```python
app.include_router(food_router)
```

Provider 运行时负责人应注入实际加载食物类别权重的 `FoodRecognitionProvider` 实现；数据库
负责人应注入 ORM Repository。两者接入前，默认 Provider 会明确返回 503，不会伪造识别结果。

## API 契约示例

### 创建识别任务

```http
POST /api/food/recognitions
Authorization: Bearer <token>
Content-Type: multipart/form-data

image=@meal.jpg
conf_threshold=0.35
```

```json
{
  "code": 201,
  "message": "食物识别完成",
  "data": {
    "recognition_id": "e1c2b46e-6f4c-497a-a3d1-5e2218863f3b",
    "status": "recognized",
    "image_object_name": "food-recognitions/8/e1c2b46e-6f4c-497a-a3d1-5e2218863f3b.jpg",
    "provider": "yolo",
    "model_version": "food-yolo-v1",
    "conf_threshold": 0.35,
    "raw_detections": [
      {
        "key": "tomato",
        "name": "番茄",
        "confidence": 0.96,
        "bbox": {"x1": 12, "y1": 24, "x2": 156, "y2": 203},
        "source": "yolo"
      }
    ],
    "confirmed_ingredients": [],
    "created_at": "2026-07-14T12:00:00",
    "updated_at": "2026-07-14T12:00:00",
    "confirmed_at": null
  }
}
```

### 确认食材快照

```http
PUT /api/food/recognitions/e1c2b46e-6f4c-497a-a3d1-5e2218863f3b/confirmed-ingredients
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "confirmed_ingredients": [
    {"key": "tomato", "name": "番茄", "quantity": "2", "unit": "个", "source": "yolo"},
    {"key": "egg", "name": "鸡蛋", "quantity": "3", "unit": "个", "source": "manual"}
  ]
}
```

成功后响应中的 `status` 为 `confirmed`，`confirmed_at` 有值，且
`confirmed_ingredients` 与请求体完整一致。
