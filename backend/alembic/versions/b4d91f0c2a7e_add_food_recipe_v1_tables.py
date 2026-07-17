"""新增 Food Recognition、Recipe 表并关联 Chat Session。

Revision ID: b4d91f0c2a7e
Revises: 86c3434a7981
Create Date: 2026-07-15
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b4d91f0c2a7e"
down_revision: Union[str, Sequence[str], None] = "86c3434a7981"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "food_recognition_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column(
            "image_object_name", sa.String(length=500), nullable=False, comment="MinIO 对象名"
        ),
        sa.Column("status", sa.String(length=20), nullable=False, comment="识别状态"),
        sa.Column("provider", sa.String(length=20), nullable=False, comment="食品识别模型提供方"),
        sa.Column("model_version", sa.String(length=100), nullable=False, comment="模型版本"),
        sa.Column("raw_detections", sa.JSON(), nullable=False, comment="IngredientCandidate 列表"),
        sa.Column(
            "confirmed_ingredients", sa.JSON(), nullable=False, comment="ConfirmedIngredient 列表"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_recognition_tasks_user_id", "food_recognition_tasks", ["user_id"])
    op.create_index("ix_food_recognition_tasks_status", "food_recognition_tasks", ["status"])
    op.create_index(
        "ix_food_recognition_tasks_created_at", "food_recognition_tasks", ["created_at"]
    )

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, comment="所属用户"),
        sa.Column("recognition_id", sa.Integer(), nullable=False, comment="来源识别任务"),
        sa.Column("version", sa.Integer(), nullable=False, comment="菜谱版本"),
        sa.Column("recipe_data", sa.JSON(), nullable=False, comment="完整 Recipe JSON"),
        sa.Column("generator", sa.JSON(), nullable=False, comment="生成器元信息"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recognition_id"], ["food_recognition_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"])
    op.create_index("ix_recipes_recognition_id", "recipes", ["recognition_id"])

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("recipe_id", sa.Integer(), nullable=True, comment="关联菜谱"))
        batch_op.create_index("ix_chat_sessions_recipe_id", ["recipe_id"])
        batch_op.create_foreign_key(
            "fk_chat_sessions_recipe_id",
            "recipes",
            ["recipe_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_constraint("fk_chat_sessions_recipe_id", type_="foreignkey")
        batch_op.drop_index("ix_chat_sessions_recipe_id")
        batch_op.drop_column("recipe_id")

    op.drop_index("ix_recipes_recognition_id", table_name="recipes")
    op.drop_index("ix_recipes_user_id", table_name="recipes")
    op.drop_table("recipes")
    op.drop_index("ix_food_recognition_tasks_created_at", table_name="food_recognition_tasks")
    op.drop_index("ix_food_recognition_tasks_status", table_name="food_recognition_tasks")
    op.drop_index("ix_food_recognition_tasks_user_id", table_name="food_recognition_tasks")
    op.drop_table("food_recognition_tasks")
