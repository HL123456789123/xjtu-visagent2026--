"""新增菜谱、食材识别任务并关联对话

Revision ID: 17f47c61a21b
Revises: f6a7b8c9d0e1
"""

from alembic import op
import sqlalchemy as sa

revision = "17f47c61a21b"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "food_recognition_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("image_object_names", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model_version", sa.String(100)),
        sa.Column("raw_detections", sa.JSON()),
        sa.Column("confirmed_ingredients", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_food_recognition_tasks_user_id", "food_recognition_tasks", ["user_id"])
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recognition_id", sa.Integer(), sa.ForeignKey("food_recognition_tasks.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("recipe_data", sa.JSON(), nullable=False),
        sa.Column("generator", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recipes_user_id", "recipes", ["user_id"])
    op.create_index("ix_recipes_recognition_id", "recipes", ["recognition_id"])
    op.add_column(
        "chat_sessions",
        sa.Column("recipe_id", sa.Integer(), nullable=True, comment="关联菜谱 ID"),
    )
    op.create_foreign_key("fk_chat_sessions_recipe_id", "chat_sessions", "recipes", ["recipe_id"], ["id"])
    op.create_index("ix_chat_sessions_recipe_id", "chat_sessions", ["recipe_id"])


def downgrade():
    op.drop_index("ix_chat_sessions_recipe_id", table_name="chat_sessions")
    op.drop_constraint("fk_chat_sessions_recipe_id", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "recipe_id")
    op.drop_index("ix_recipes_recognition_id", table_name="recipes")
    op.drop_index("ix_recipes_user_id", table_name="recipes")
    op.drop_table("recipes")
    op.drop_index("ix_food_recognition_tasks_user_id", table_name="food_recognition_tasks")
    op.drop_table("food_recognition_tasks")
