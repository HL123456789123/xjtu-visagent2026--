# 数据库契约 v1 - 菜谱模块

**冻结时间**：2026-07-10  
**负责人**：陈煜君  
**状态**：已冻结

---

## 一、涉及的表

本模块涉及以下表的新增或修改：

| 表名 | 操作 | 说明 |
|------|------|------|
| `food_recognition_tasks` | 新增 | 食物识别任务记录 |
| `recipes` | 新增 | 菜谱主表 |
| `chat_sessions` | 修改 | 增加 `recipe_id` 外键 |
| `users` | 关联 | 已有表，通过 `user_id` 关联 |

---

## 二、新增表结构

### 1. food_recognition_tasks（食物识别任务表）

记录每次图片识别的结果和用户确认状态。

| 字段 | 类型 | 可空 | 默认值 | 说明 |
|------|------|------|--------|------|
| id | INTEGER | PK 自增 | - | 主键 |
| user_id | INTEGER | FK(users.id) | NOT NULL | 操作用户 |
| object_name | VARCHAR(500) | NOT NULL | - | MinIO 中的对象名 |
| image_url | VARCHAR(500) | NULL | - | 图片访问 URL |
| status | VARCHAR(20) | NOT NULL | 'pending' | pending/processing/completed/failed |
| provider | VARCHAR(50) | NOT NULL | 'mock' | 识别提供者：mock/yolo |
| model_version | VARCHAR(50) | NULL | - | 模型版本 |
|confidence_threshold | FLOAT | NULL|0.5|置信度阈值|
| detected_ingredients | JSON | NULL | - | 原始识别结果 |
| confirmed_ingredients | JSON | NULL | - | 用户确认后的食材列表 |
| total_detections | INTEGER | NOT NULL | 0 | 原始检测数量 |
| servings | INTEGER | NULL | 2 | 份数（用户可调整） |
| inference_time_ms | FLOAT | NULL | - | 推理耗时（毫秒） |
| error_message | TEXT | NULL | - | 失败时的错误信息 |
| created_at | DATETIME | NOT NULL | NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL | NOW() | 更新时间 |

**索引**：
- `idx_food_recognition_tasks_user_id` (user_id)
- `idx_food_recognition_tasks_status` (status)
- `idx_food_recognition_tasks_created_at` (created_at)

**detected_ingredients JSON 格式**（原始识别输出）：
```json
[
    {"class_name": "tomato", "class_name_cn": "番茄", "confidence": 0.95},
    {"class_name": "egg", "class_name_cn": "鸡蛋", "confidence": 0.88}
]
```

confirmed_ingredients JSON 格式（用户确认后）：

```json
[
    {"name": "番茄", "amount": 2, "unit": "个", "category": "蔬菜"},
    {"name": "鸡蛋", "amount": 3, "unit": "个", "category": "蛋类"}
]
```

### 2. recipes（菜谱表）
存储生成的菜谱，每次更新会生成新版本。

字段	类型	可空	默认值	说明
id	INTEGER	PK 自增	-	主键
recognition_id	INTEGER	FK(food_recognition_tasks.id)	NOT NULL	关联的识别任务
user_id	INTEGER	FK(users.id)	NOT NULL	创建者
title	VARCHAR(200)	NOT NULL	-	菜名
description	TEXT	NULL	-	简介
ingredients	JSON	NOT NULL	-	食材列表（结构化）
steps	JSON	NOT NULL	-	步骤列表（结构化）
nutrition	JSON	NULL	-	营养信息
cuisine	VARCHAR(50)	NULL	-	菜系
difficulty	VARCHAR(20)	NOT NULL	'medium'	easy/medium/hard
prep_time_minutes	INTEGER	NOT NULL	0	准备时间（分钟）
cook_time_minutes	INTEGER	NOT NULL	0	烹饪时间（分钟）
servings	INTEGER	NOT NULL	2	几人份
image_url	VARCHAR(500)	NULL	-	成品图 URL（预留）
source	VARCHAR(20)	NOT NULL	'ai'	来源：ai/manual
version	INTEGER	NOT NULL	1	版本号，每次更新 +1
is_deleted	BOOLEAN	NOT NULL	false	软删除标记
created_at	DATETIME	NOT NULL	NOW()	创建时间
updated_at	DATETIME	NOT NULL	NOW()	更新时间

索引：

idx_recipes_user_id (user_id)

idx_recipes_recognition_id (recognition_id)

idx_recipes_user_created (user_id, created_at DESC)

idx_recipes_user_deleted (user_id, is_deleted)

ingredients JSON 格式：

```json
[
    {"name": "番茄", "amount": 200, "unit": "克", "category": "蔬菜"},
    {"name": "鸡蛋", "amount": 3, "unit": "个", "category": "蛋类"}
]```
steps JSON 格式：

```json
[
    {"step_number": 1, "description": "番茄切块", "duration_minutes": 2},
    {"step_number": 2, "description": "鸡蛋打散", "duration_minutes": 1}
]
```
nutrition JSON 格式：

```json
{
    "calories": 220.0,
    "protein": 12.0,
    "fat": 15.0,
    "carbs": 10.0,
    "fiber": 2.0,
    "disclaimer": "本营养数据为AI估算值，仅供参考，不构成医学建议。"
}
```

## 三、修改现有表
3. chat_sessions（聊天会话表）- 新增字段
字段	类型	可空	默认值	说明
recipe_id	INTEGER	FK(recipes.id)	NULL	-	关联的菜谱 ID
索引：

idx_chat_sessions_recipe_id (recipe_id)

## 四、表关系图
text
users (现有)
  ├─ 1 : N → food_recognition_tasks (user_id)
  ├─ 1 : N → recipes (user_id)
  └─ 1 : N → chat_sessions (user_id)

food_recognition_tasks
  └─ 1 : 1 → recipes (recognition_id)  [一个识别任务最多生成一个菜谱]

recipes
  └─ 1 : N → chat_sessions (recipe_id)  [一个菜谱可关联多个会话]
## 五、迁移策略
### 5.1 迁移文件命名
text
alembic/versions/20260710_xxx_add_recipe_tables.py
### 5.2 升级路径
新增 food_recognition_tasks 表

新增 recipes 表

chat_sessions 表增加 recipe_id 外键（可为空）

### 5.3 回滚策略
删除 recipes 表

删除 food_recognition_tasks 表

chat_sessions 表移除 recipe_id 字段

### 5.4 数据库兼容性
SQLite：测试环境使用，JSON 字段用 JSON 类型，外键约束需手动启用

PostgreSQL：生产环境使用，JSON 字段用 JSONB 类型（通过 SQLAlchemy 的 JSON 自动适配）

迁移脚本中使用 sa.JSON，由 SQLAlchemy 自动适配两种数据库

## 六、数据示例
### 6.1 完整菜谱数据示例
json
{
    "id": 1,
    "recognition_id": 123,
    "user_id": 1,
    "title": "番茄炒蛋",
    "description": "经典家常菜，营养丰富",
    "ingredients": [
        {"name": "番茄", "amount": 200, "unit": "克", "category": "蔬菜"},
        {"name": "鸡蛋", "amount": 3, "unit": "个", "category": "蛋类"}
    ],
    "steps": [
        {"step_number": 1, "description": "番茄切块", "duration_minutes": 2},
        {"step_number": 2, "description": "鸡蛋打散", "duration_minutes": 1},
        {"step_number": 3, "description": "炒制", "duration_minutes": 5}
    ],
    "nutrition": {
        "calories": 220.0,
        "protein": 12.0,
        "fat": 15.0,
        "carbs": 10.0,
        "fiber": 2.0,
        "disclaimer": "本营养数据为AI估算值，仅供参考，不构成医学建议。"
    },
    "cuisine": "chinese",
    "difficulty": "easy",
    "prep_time_minutes": 5,
    "cook_time_minutes": 10,
    "servings": 2,
    "source": "ai",
    "version": 1,
    "created_at": "2026-07-10T10:00:00",
    "updated_at": "2026-07-10T10:00:00"
}
## 七、验收标准
全新数据库执行 alembic upgrade head 成功

三张表结构正确，字段、索引、外键与本文档一致

从已有数据库执行迁移，chat_sessions 的 recipe_id 列为空（向后兼容）

升级后 alembic history 显示单一 head

回滚后表结构恢复到迁移前状态

text
