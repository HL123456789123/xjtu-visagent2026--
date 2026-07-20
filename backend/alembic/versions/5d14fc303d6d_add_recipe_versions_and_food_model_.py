"""add recipe versions and food model registry

Revision ID: 5d14fc303d6d
Revises: a7e1c9f42d6b
Create Date: 2026-07-20 04:46:27.418892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "5d14fc303d6d"
down_revision: Union[str, Sequence[str], None] = "a7e1c9f42d6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "food_model_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("task", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("weights_path", sa.String(length=500), nullable=False),
        sa.Column("classes_path", sa.String(length=500), nullable=False),
        sa.Column("weight_sha256", sa.String(length=64), nullable=False),
        sa.Column("classes_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("class_count", sa.Integer(), nullable=False),
        sa.Column("classes", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("activated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_food_model_versions_is_active"),
        "food_model_versions",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_model_versions_status"),
        "food_model_versions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_model_versions_uploaded_by"),
        "food_model_versions",
        ["uploaded_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_food_model_versions_version"),
        "food_model_versions",
        ["version"],
        unique=True,
    )
    op.create_index(
        "uq_food_model_versions_single_active",
        "food_model_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "recipe_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recipe_data", sa.JSON(), nullable=False),
        sa.Column("change_type", sa.String(length=30), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["chat_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recipe_id",
            "version",
            name="uq_recipe_versions_recipe_version",
        ),
    )
    op.create_index(
        op.f("ix_recipe_versions_recipe_id"),
        "recipe_versions",
        ["recipe_id"],
        unique=False,
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "recipe_version",
            sa.Integer(),
            nullable=True,
            comment="该回复产生的菜谱版本",
        ),
    )
    op.add_column(
        "chat_sessions",
        sa.Column(
            "context_summary",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
    )
    op.add_column(
        "chat_sessions",
        sa.Column("summary_through_message_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chat_sessions", "summary_through_message_id")
    op.drop_column("chat_sessions", "context_summary")
    op.drop_column("chat_messages", "recipe_version")

    op.drop_index(
        op.f("ix_recipe_versions_recipe_id"),
        table_name="recipe_versions",
    )
    op.drop_table("recipe_versions")

    op.drop_index(
        "uq_food_model_versions_single_active",
        table_name="food_model_versions",
    )
    op.drop_index(
        op.f("ix_food_model_versions_version"),
        table_name="food_model_versions",
    )
    op.drop_index(
        op.f("ix_food_model_versions_uploaded_by"),
        table_name="food_model_versions",
    )
    op.drop_index(
        op.f("ix_food_model_versions_status"),
        table_name="food_model_versions",
    )
    op.drop_index(
        op.f("ix_food_model_versions_is_active"),
        table_name="food_model_versions",
    )
    op.drop_table("food_model_versions")
