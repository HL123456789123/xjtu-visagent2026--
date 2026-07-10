"""make training_tasks.model_id nullable

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 将 model_id 改为 nullable，训练任务不再强制关联已有模型
    op.alter_column(
        "training_tasks",
        "model_id",
        existing_type=sa.Integer(),
        nullable=True,
        existing_comment="关联模型",
        new_comment="关联模型（可选，训练成功后自动创建新模型）",
    )


def downgrade() -> None:
    # 回滚时需要先处理 model_id 为 NULL 的记录
    op.alter_column(
        "training_tasks",
        "model_id",
        existing_type=sa.Integer(),
        nullable=False,
        existing_comment="关联模型（可选，训练成功后自动创建新模型）",
        new_comment="关联模型",
    )
