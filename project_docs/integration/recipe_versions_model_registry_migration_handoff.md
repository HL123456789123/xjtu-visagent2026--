# Recipe 版本与 Food 模型注册 Migration 记录

日期：2026-07-20
目标分支：`codex/recipe-versions-model-admin`
执行授权：项目负责人于 2026-07-20 明确授权 Codex 执行

## 当前状态

Migration `5d14fc303d6d_add_recipe_versions_and_food_model_.py` 已创建，父 revision 为 `a7e1c9f42d6b`，迁移链保持单一 head。自动生成候选中出现的旧表索引、注释、外键和 `users.is_superuser` 等无关漂移均已人工移除。

迁移先在由正式本地库备份恢复出的 `visagent_migration_test` 上完成 `upgrade -> downgrade -> upgrade`，再升级正式本地库。验证期间 19 个用户、21 条菜谱和 20 个会话数量保持不变，既有会话的 `context_summary` 无空值。

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

## 验证与部署结果

已完成：

- 独立数据库首次升级到 `5d14fc303d6d`。
- 独立数据库降级到 `a7e1c9f42d6b`，新增表和列均被撤销，旧数据数量不变。
- 独立数据库再次升级到 `5d14fc303d6d`。
- 正式本地库升级到 `5d14fc303d6d`。
- backend/frontend 镜像重建并强制重建容器。
- `alembic heads` 与 `alembic current` 均为 `5d14fc303d6d (head)`。
- backend、frontend、PostgreSQL、Redis、MinIO 均运行正常。

降级会删除新版本快照与模型注册数据，只用于迁移验证或明确回滚；生产回滚前仍须单独备份数据库与模型注册命名卷。
