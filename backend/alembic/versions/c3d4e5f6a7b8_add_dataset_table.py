"""add: 新增数据集管理表 datasets

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 datasets 表
    op.create_table(
        'datasets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='注册用户'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='数据集名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('path', sa.String(length=500), nullable=False, comment='数据集根目录路径'),
        sa.Column('yaml_path', sa.String(length=500), nullable=False, comment='data.yaml 路径'),
        sa.Column('num_images', sa.Integer(), server_default='0', comment='图片数量'),
        sa.Column('num_classes', sa.Integer(), server_default='0', comment='类别数'),
        sa.Column('class_names', sa.JSON(), nullable=True, comment='类别名称列表'),
        sa.Column('format', sa.String(length=20), server_default='yolo', comment='标注格式：yolo/voc/coco'),
        sa.Column('status', sa.String(length=20), server_default='active', comment='状态：active/invalid'),
        sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_datasets_user_id'), 'datasets', ['user_id'], unique=False)
    op.create_index(op.f('ix_datasets_status'), 'datasets', ['status'], unique=False)

    # 给 training_tasks 添加 dataset_id 列
    op.add_column(
        'training_tasks',
        sa.Column('dataset_id', sa.Integer(), nullable=True, comment='关联数据集'),
    )
    op.create_index(op.f('ix_training_tasks_dataset_id'), 'training_tasks', ['dataset_id'], unique=False)
    op.create_foreign_key(
        'fk_training_tasks_dataset_id',
        'training_tasks',
        'datasets',
        ['dataset_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_training_tasks_dataset_id', 'training_tasks', type_='foreignkey')
    op.drop_index(op.f('ix_training_tasks_dataset_id'), table_name='training_tasks')
    op.drop_column('training_tasks', 'dataset_id')

    op.drop_index(op.f('ix_datasets_status'), table_name='datasets')
    op.drop_index(op.f('ix_datasets_user_id'), table_name='datasets')
    op.drop_table('datasets')
