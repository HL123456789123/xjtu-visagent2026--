"""add scene_id to datasets

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 为 datasets 表添加 scene_id 字段，关联检测场景
    op.add_column(
        "datasets",
        sa.Column(
            "scene_id",
            sa.Integer(),
            sa.ForeignKey("detection_scenes.id"),
            nullable=True,
            comment="关联检测场景",
        ),
    )
    # 添加索引
    op.create_index(op.f("ix_datasets_scene_id"), "datasets", ["scene_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_datasets_scene_id"), table_name="datasets")
    op.drop_column("datasets", "scene_id")
