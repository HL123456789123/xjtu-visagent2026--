# Recipe 版本与 Food 模型注册 Migration 交接

日期：2026-07-20
目标分支：`codex/recipe-versions-model-admin`
数据库 owner：绕家辉

## 当前状态

ORM、Repository、Service、API 和测试已经按本文件所列结构实现。依据仓库 `AGENTS.md`，本次没有创建或修改 `backend/alembic/versions/`。数据库 owner 合入单链 migration 前，新版 Docker 可以构建和启动，但调用菜谱版本或 Food 模型注册业务会因缺表/缺列失败，因此不得宣称新版 Docker 业务验收通过。

2026-07-20 本机复核结果：`alembic heads` 与 `alembic current` 均为单一 `a7e1c9f42d6b (head)`；现有数据库尚无 `recipe_versions`、`food_model_versions`，也尚无下文列出的三个新增列。为保护当前演示数据，本轮没有用新版后端重建正在运行的容器。

## 结构变更

### 新表 `recipe_versions`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | Integer | PK，自增 |
| `recipe_id` | Integer | FK `recipes.id`，非空，索引 |
| `version` | Integer | 非空 |
| `recipe_data` | JSON | 非空 |
| `change_type` | String(30) | 非空，默认 `generated` |
| `change_reason` | Text | 可空 |
| `source_message_id` | Integer | FK `chat_messages.id`，可空 |
| `source_version` | Integer | 可空 |
| `created_at` | DateTime(timezone=True) | 非空 |

唯一约束：`uq_recipe_versions_recipe_version (recipe_id, version)`。

### 表 `chat_sessions` 新列

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `context_summary` | Text | 非空，应用默认和 server default 均为空字符串 |
| `summary_through_message_id` | Integer | 可空 |

### 表 `chat_messages` 新列

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `recipe_version` | Integer | 可空 |

### 新表 `food_model_versions`

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `id` | Integer | PK，自增 |
| `name` | String(100) | 非空 |
| `version` | String(100) | 非空、唯一、索引 |
| `task` | String(20) | 非空，应用只允许 `detect/classify` |
| `status` | String(20) | 非空、默认 `validating`、索引 |
| `weights_path` | String(500) | 非空，仅后端内部使用 |
| `classes_path` | String(500) | 非空，仅后端内部使用 |
| `weight_sha256` | String(64) | 非空 |
| `classes_sha256` | String(64) | 非空 |
| `file_size` | BigInteger | 非空 |
| `class_count` | Integer | 非空 |
| `classes` | JSON | 非空、默认空数组 |
| `manifest` | JSON | 非空、默认空对象 |
| `is_active` | Boolean | 非空、默认 false、索引 |
| `validation_error` | Text | 可空 |
| `uploaded_by` | Integer | FK `users.id`，非空、索引 |
| `activated_by` | Integer | FK `users.id`，可空 |
| `created_at` | DateTime(timezone=True) | 非空 |
| `validated_at` | DateTime(timezone=True) | 可空 |
| `activated_at` | DateTime(timezone=True) | 可空 |

建议在 PostgreSQL 增加“最多一个 `is_active = true`”的部分唯一索引；ORM 仍在事务内先停用旧记录再启用新记录。

## 数据处理

1. migration 只创建结构和安全默认值，不伪造旧 Recipe 历史。
2. `chat_sessions.context_summary` 对既有行回填空字符串后设为非空。
3. 既有 Recipe 在首次访问版本接口或产生下一次更新时，由 Repository 把当前 `recipe_data` 和当前 `version` 写成一条 `backfill` 快照。
4. 不推测 v1 到当前版本之间已经丢失的内容。
5. 不删除旧角色、旧检测/训练/数据集表及其历史数据。

## Owner 操作与复核

从 `backend/` 执行，并先确认目标为允许操作的本地/测试库：

```powershell
uv run alembic current
uv run alembic heads
uv run alembic revision --autogenerate -m "add recipe versions and food model registry"
uv run alembic upgrade head
uv run alembic current
uv run pytest
```

Owner 需要人工复核：单一 head、部分唯一索引、server default、upgrade/downgrade 顺序、FK 创建顺序，以及 downgrade 是否会明确丢弃新版本数据。migration 文件应由数据库 owner 单独提交，本交接不代替该提交。
