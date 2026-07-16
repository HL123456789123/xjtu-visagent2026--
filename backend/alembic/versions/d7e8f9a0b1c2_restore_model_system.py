"""恢复模型、数据集及场景绑定体系

Revision ID: d7e8f9a0b1c2
Revises: c3d6e8f4a2b1
Create Date: 2026-07-16 23:10:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c3d6e8f4a2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """恢复合并时遗漏的模型体系，并迁移旧训练与版本记录。"""

    op.create_table(
        "models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, comment="模型名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="模型描述"),
        sa.Column(
            "base_architecture",
            sa.String(length=50),
            server_default="yolo26n",
            nullable=True,
            comment="基础架构：yolo26n/s/m/l/x",
        ),
        sa.Column("category", sa.String(length=50), nullable=False, comment="模型分类"),
        sa.Column("class_names", sa.JSON(), nullable=False, comment="类别列表"),
        sa.Column("class_names_cn", sa.JSON(), nullable=True, comment="类别中文名映射"),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="active",
            nullable=True,
            comment="状态：active/archived",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
            comment="是否启用",
        ),
        sa.Column("created_by", sa.Integer(), nullable=True, comment="创建人"),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.Column("updated_at", sa.DateTime(), nullable=True, comment="更新时间"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_models_created_by_users"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_models_name"),
    )

    op.create_table(
        "scene_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False, comment="场景 ID"),
        sa.Column("model_id", sa.Integer(), nullable=False, comment="模型 ID"),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.false(), nullable=True, comment="是否默认"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True, comment="创建时间"),
        sa.ForeignKeyConstraint(
            ["scene_id"], ["detection_scenes.id"], name="fk_scene_models_scene_id"
        ),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], name="fk_scene_models_model_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_id", "model_id", name="uq_scene_models_pair"),
    )
    op.create_index("ix_scene_models_scene_id", "scene_models", ["scene_id"])
    op.create_index("ix_scene_models_model_id", "scene_models", ["model_id"])

    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="注册用户"),
        sa.Column("name", sa.String(length=100), nullable=False, comment="数据集名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="描述"),
        sa.Column("path", sa.String(length=500), nullable=False, comment="数据集根目录路径"),
        sa.Column("yaml_path", sa.String(length=500), nullable=False, comment="data.yaml 路径"),
        sa.Column("num_images", sa.Integer(), server_default="0", nullable=True),
        sa.Column("num_classes", sa.Integer(), server_default="0", nullable=True),
        sa.Column("class_names", sa.JSON(), nullable=True),
        sa.Column("format", sa.String(length=20), server_default="yolo", nullable=True),
        sa.Column("scene_id", sa.Integer(), nullable=True, comment="关联检测场景"),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_datasets_user_id"),
        sa.ForeignKeyConstraint(["scene_id"], ["detection_scenes.id"], name="fk_datasets_scene_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_datasets_user_id", "datasets", ["user_id"])
    op.create_index("ix_datasets_scene_id", "datasets", ["scene_id"])
    op.create_index("ix_datasets_status", "datasets", ["status"])

    # 把旧 ModelVersion 的场景、名称和架构拆分为 Model 与 SceneModel。
    op.add_column("model_versions", sa.Column("model_id", sa.Integer(), nullable=True))
    op.add_column(
        "model_versions",
        sa.Column("source", sa.String(length=20), server_default="training", nullable=True),
    )
    op.execute(
        """
        INSERT INTO models (
            name, description, base_architecture, category, class_names,
            class_names_cn, status, is_enabled, created_at, updated_at
        )
        SELECT DISTINCT ON (mv.model_name)
            mv.model_name,
            '从历史模型版本迁移创建',
            CASE
                WHEN mv.model_type IN ('yolov11n', 'yolo11n') THEN 'yolo26n'
                WHEN mv.model_type IN ('yolov11s', 'yolo11s') THEN 'yolo26s'
                WHEN mv.model_type IN ('yolov11m', 'yolo11m') THEN 'yolo26m'
                WHEN mv.model_type IN ('yolov11l', 'yolo11l') THEN 'yolo26l'
                WHEN mv.model_type IN ('yolov11x', 'yolo11x') THEN 'yolo26x'
                ELSE COALESCE(mv.model_type, 'yolo26n')
            END,
            COALESCE(ds.category, 'general'),
            COALESCE(ds.class_names, CAST('[]' AS JSON)),
            ds.class_names_cn,
            'active',
            true,
            mv.created_at,
            mv.created_at
        FROM model_versions mv
        LEFT JOIN detection_scenes ds ON ds.id = mv.scene_id
        ORDER BY mv.model_name, mv.created_at, mv.id
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE model_versions mv
        SET model_id = m.id,
            source = CASE WHEN mv.training_task_id IS NULL THEN 'upload' ELSE 'training' END
        FROM models m
        WHERE m.name = mv.model_name
        """
    )
    op.execute(
        """
        INSERT INTO scene_models (scene_id, model_id, is_default, created_at)
        SELECT DISTINCT mv.scene_id, mv.model_id, false, mv.created_at
        FROM model_versions mv
        WHERE mv.scene_id IS NOT NULL AND mv.model_id IS NOT NULL
        ON CONFLICT (scene_id, model_id) DO NOTHING
        """
    )

    # 已有场景来自旧版种子数据；为它们补齐逻辑模型和默认绑定。
    op.execute(
        """
        INSERT INTO models (
            name, description, base_architecture, category, class_names,
            class_names_cn, status, is_enabled, created_at, updated_at
        )
        SELECT
            ds.display_name || '模型',
            ds.description || '（默认模型）',
            'yolo26n',
            ds.category,
            ds.class_names,
            ds.class_names_cn,
            'active',
            true,
            ds.created_at,
            ds.updated_at
        FROM detection_scenes ds
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO scene_models (scene_id, model_id, is_default, created_at)
        SELECT ds.id, m.id, true, ds.created_at
        FROM detection_scenes ds
        JOIN models m ON m.name = ds.display_name || '模型'
        ON CONFLICT (scene_id, model_id)
        DO UPDATE SET is_default = EXCLUDED.is_default
        """
    )

    missing_versions = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM model_versions WHERE model_id IS NULL")
    )
    if missing_versions:
        raise RuntimeError(f"仍有 {missing_versions} 条模型版本无法关联逻辑模型")

    op.create_foreign_key(
        "fk_model_versions_model_id",
        "model_versions",
        "models",
        ["model_id"],
        ["id"],
    )
    op.alter_column("model_versions", "model_id", existing_type=sa.Integer(), nullable=False)
    op.create_index("ix_model_versions_model_id", "model_versions", ["model_id"])
    op.drop_column("model_versions", "scene_id")
    op.drop_column("model_versions", "model_name")
    op.drop_column("model_versions", "model_type")

    # 把旧 TrainingTask 的场景和 model_name 迁移到新模型、数据集体系。
    op.add_column("training_tasks", sa.Column("model_id", sa.Integer(), nullable=True))
    op.add_column(
        "training_tasks", sa.Column("base_architecture", sa.String(length=50), nullable=True)
    )
    op.add_column(
        "training_tasks", sa.Column("checkpoint_path", sa.String(length=500), nullable=True)
    )
    op.add_column(
        "training_tasks",
        sa.Column("last_checkpoint_epoch", sa.Integer(), server_default="0", nullable=True),
    )
    op.add_column(
        "training_tasks",
        sa.Column("set_as_default", sa.Boolean(), server_default=sa.false(), nullable=True),
    )
    op.add_column("training_tasks", sa.Column("dataset_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE training_tasks
        SET base_architecture = CASE
            WHEN model_name IN ('yolov11n', 'yolo11n') THEN 'yolo26n'
            WHEN model_name IN ('yolov11s', 'yolo11s') THEN 'yolo26s'
            WHEN model_name IN ('yolov11m', 'yolo11m') THEN 'yolo26m'
            WHEN model_name IN ('yolov11l', 'yolo11l') THEN 'yolo26l'
            WHEN model_name IN ('yolov11x', 'yolo11x') THEN 'yolo26x'
            ELSE COALESCE(model_name, 'yolo26n')
        END
        """
    )
    op.execute(
        """
        INSERT INTO models (
            name, description, base_architecture, category, class_names,
            class_names_cn, status, is_enabled, created_by, created_at, updated_at
        )
        SELECT
            '训练模型_' || tt.id,
            '从历史训练任务迁移创建',
            tt.base_architecture,
            COALESCE(ds.category, 'general'),
            COALESCE(ds.class_names, CAST('[]' AS JSON)),
            ds.class_names_cn,
            'active',
            true,
            tt.user_id,
            tt.created_at,
            tt.updated_at
        FROM training_tasks tt
        LEFT JOIN detection_scenes ds ON ds.id = tt.scene_id
        ON CONFLICT (name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE training_tasks tt
        SET model_id = m.id
        FROM models m
        WHERE m.name = '训练模型_' || tt.id
        """
    )
    op.execute(
        """
        INSERT INTO scene_models (scene_id, model_id, is_default, created_at)
        SELECT tt.scene_id, tt.model_id, false, tt.created_at
        FROM training_tasks tt
        WHERE tt.scene_id IS NOT NULL AND tt.model_id IS NOT NULL
        ON CONFLICT (scene_id, model_id) DO NOTHING
        """
    )

    op.create_foreign_key(
        "fk_training_tasks_model_id", "training_tasks", "models", ["model_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_training_tasks_dataset_id", "training_tasks", "datasets", ["dataset_id"], ["id"]
    )
    op.create_index("ix_training_tasks_model_id", "training_tasks", ["model_id"])
    op.create_index("ix_training_tasks_dataset_id", "training_tasks", ["dataset_id"])
    op.create_index("ix_training_tasks_status", "training_tasks", ["status"])
    op.drop_column("training_tasks", "scene_id")
    op.drop_column("training_tasks", "model_name")


def downgrade() -> None:
    """恢复迁移前的旧模型版本与训练任务字段。"""

    op.add_column("training_tasks", sa.Column("scene_id", sa.Integer(), nullable=True))
    op.add_column("training_tasks", sa.Column("model_name", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE training_tasks tt
        SET scene_id = (
                SELECT sm.scene_id FROM scene_models sm
                WHERE sm.model_id = tt.model_id ORDER BY sm.is_default DESC, sm.id LIMIT 1
            ),
            model_name = tt.base_architecture
        """
    )
    op.create_foreign_key(
        "fk_training_tasks_scene_id",
        "training_tasks",
        "detection_scenes",
        ["scene_id"],
        ["id"],
    )
    op.create_index("ix_training_tasks_scene_id", "training_tasks", ["scene_id"])
    op.drop_index("ix_training_tasks_status", table_name="training_tasks")
    op.drop_index("ix_training_tasks_dataset_id", table_name="training_tasks")
    op.drop_index("ix_training_tasks_model_id", table_name="training_tasks")
    op.drop_constraint("fk_training_tasks_dataset_id", "training_tasks", type_="foreignkey")
    op.drop_constraint("fk_training_tasks_model_id", "training_tasks", type_="foreignkey")
    op.drop_column("training_tasks", "dataset_id")
    op.drop_column("training_tasks", "set_as_default")
    op.drop_column("training_tasks", "last_checkpoint_epoch")
    op.drop_column("training_tasks", "checkpoint_path")
    op.drop_column("training_tasks", "base_architecture")
    op.drop_column("training_tasks", "model_id")

    op.add_column("model_versions", sa.Column("scene_id", sa.Integer(), nullable=True))
    op.add_column("model_versions", sa.Column("model_name", sa.String(length=100), nullable=True))
    op.add_column("model_versions", sa.Column("model_type", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE model_versions mv
        SET scene_id = (
                SELECT sm.scene_id FROM scene_models sm
                WHERE sm.model_id = mv.model_id ORDER BY sm.is_default DESC, sm.id LIMIT 1
            ),
            model_name = m.name,
            model_type = m.base_architecture
        FROM models m
        WHERE m.id = mv.model_id
        """
    )
    op.create_foreign_key(
        "fk_model_versions_scene_id",
        "model_versions",
        "detection_scenes",
        ["scene_id"],
        ["id"],
    )
    op.create_index("ix_model_versions_scene_id", "model_versions", ["scene_id"])
    op.drop_index("ix_model_versions_model_id", table_name="model_versions")
    op.drop_constraint("fk_model_versions_model_id", "model_versions", type_="foreignkey")
    op.drop_column("model_versions", "source")
    op.drop_column("model_versions", "model_id")

    op.drop_index("ix_datasets_status", table_name="datasets")
    op.drop_index("ix_datasets_scene_id", table_name="datasets")
    op.drop_index("ix_datasets_user_id", table_name="datasets")
    op.drop_table("datasets")
    op.drop_index("ix_scene_models_model_id", table_name="scene_models")
    op.drop_index("ix_scene_models_scene_id", table_name="scene_models")
    op.drop_table("scene_models")
    op.drop_table("models")
