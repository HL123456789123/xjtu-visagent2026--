"""Add final V1.1 Food and Recipe storage plus the Chat recipe link.

Revision ID: a7e1c9f42d6b
Revises: f6a7b8c9d0e1
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7e1c9f42d6b"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "food_recognition_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("image_object_names", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("raw_detections", sa.JSON(), nullable=False),
        sa.Column("confirmed_ingredients", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_food_recognition_tasks_user_id", "food_recognition_tasks", ["user_id"]
    )
    op.create_index(
        "ix_food_recognition_tasks_status", "food_recognition_tasks", ["status"]
    )
    op.create_index(
        "ix_food_recognition_tasks_created_at", "food_recognition_tasks", ["created_at"]
    )

    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recognition_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recipe_data", sa.JSON(), nullable=False),
        sa.Column("generator", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recognition_id"], ["food_recognition_tasks.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"])
    op.create_index("ix_recipes_recognition_id", "recipes", ["recognition_id"])

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("recipe_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_chat_sessions_recipe_id", ["recipe_id"])
        batch_op.create_foreign_key(
            "fk_chat_sessions_recipe_id", "recipes", ["recipe_id"], ["id"]
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
