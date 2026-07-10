"""migrate: YOLO11 升级到 YOLO26 - 更新 base_architecture 字段

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# YOLO11 到 YOLO26 的架构名称映射
ARCHITECTURE_MAPPING = {
    'yolov11n': 'yolo26n',
    'yolov11s': 'yolo26s',
    'yolov11m': 'yolo26m',
    'yolov11l': 'yolo26l',
    'yolov11x': 'yolo26x',
    'yolo11n': 'yolo26n',
    'yolo11s': 'yolo26s',
    'yolo11m': 'yolo26m',
    'yolo11l': 'yolo26l',
    'yolo11x': 'yolo26x',
}


def upgrade() -> None:
    """升级：将 YOLO11 架构名称更新为 YOLO26"""
    
    # 更新 models 表
    for old_arch, new_arch in ARCHITECTURE_MAPPING.items():
        op.execute(
            f"UPDATE models SET base_architecture = '{new_arch}' WHERE base_architecture = '{old_arch}'"
        )
    
    # 更新 training_tasks 表
    for old_arch, new_arch in ARCHITECTURE_MAPPING.items():
        op.execute(
            f"UPDATE training_tasks SET base_architecture = '{new_arch}' WHERE base_architecture = '{old_arch}'"
        )
    
    # 更新列注释
    op.execute("COMMENT ON COLUMN models.base_architecture IS '基础架构：yolo26n/s/m/l/x'")
    op.execute("COMMENT ON COLUMN training_tasks.base_architecture IS '基础架构：yolo26n/s/m/l/x'")


def downgrade() -> None:
    """降级：将 YOLO26 架构名称恢复为 YOLO11"""
    
    # 反向映射
    REVERSE_MAPPING = {v: k for k, v in ARCHITECTURE_MAPPING.items()}
    
    # 恢复 models 表（使用 yolov11n 格式）
    for new_arch, old_arch in REVERSE_MAPPING.items():
        # 降级时统一使用 yolov11 格式
        old_arch_v = old_arch.replace('yolo11', 'yolov11')
        op.execute(
            f"UPDATE models SET base_architecture = '{old_arch_v}' WHERE base_architecture = '{new_arch}'"
        )
    
    # 恢复 training_tasks 表
    for new_arch, old_arch in REVERSE_MAPPING.items():
        old_arch_v = old_arch.replace('yolo11', 'yolov11')
        op.execute(
            f"UPDATE training_tasks SET base_architecture = '{old_arch_v}' WHERE base_architecture = '{new_arch}'"
        )
    
    # 恢复列注释
    op.execute("COMMENT ON COLUMN models.base_architecture IS '基础架构：yolov11n/s/m/l/x'")
    op.execute("COMMENT ON COLUMN training_tasks.base_architecture IS '基础架构：yolov11n/s/m/l/x'")
