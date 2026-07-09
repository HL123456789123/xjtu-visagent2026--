"""refactor: 模型体系重构 - 新增 Model/SceneModel 表，重构 ModelVersion/TrainingTask

Revision ID: a1b2c3d4e5f6
Revises: 86c3434a7981
Create Date: 2026-07-06 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '86c3434a7981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(op, table_name: str, column_name: str) -> bool:
    """检查列是否已存在"""
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    ), {"t": table_name, "c": column_name})
    return result.scalar() is not None


def _table_exists(op, table_name: str) -> bool:
    """检查表是否已存在"""
    from sqlalchemy import text
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    ), {"t": table_name})
    return result.scalar() is not None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. 新增 models 表
    if not _table_exists(op, 'models'):
        op.create_table('models',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False, comment='模型名称'),
            sa.Column('description', sa.Text(), nullable=True, comment='模型描述'),
            sa.Column('base_architecture', sa.String(length=50), nullable=True, comment='基础架构：yolov11n/s/m/l/x'),
            sa.Column('category', sa.String(length=50), nullable=False, comment='模型分类'),
            sa.Column('class_names', sa.JSON(), nullable=False, comment='类别列表'),
            sa.Column('class_names_cn', sa.JSON(), nullable=True, comment='类别中文名映射'),
            sa.Column('status', sa.String(length=20), nullable=True, comment='状态：active/archived'),
            sa.Column('created_by', sa.Integer(), nullable=True, comment='创建人'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.Column('updated_at', sa.DateTime(), nullable=True, comment='更新时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name'),
            sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        )
        op.create_index(op.f('ix_models_id'), 'models', ['id'], unique=False)
    
    # 2. 新增 scene_models 表
    if not _table_exists(op, 'scene_models'):
        op.create_table('scene_models',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('scene_id', sa.Integer(), nullable=False, comment='场景ID'),
            sa.Column('model_id', sa.Integer(), nullable=False, comment='模型ID'),
            sa.Column('is_default', sa.Boolean(), nullable=True, comment='是否为该场景的默认模型'),
            sa.Column('created_at', sa.DateTime(), nullable=True, comment='创建时间'),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['scene_id'], ['detection_scenes.id']),
            sa.ForeignKeyConstraint(['model_id'], ['models.id']),
        )
        op.create_index(op.f('ix_scene_models_scene_id'), 'scene_models', ['scene_id'], unique=False)
        op.create_index(op.f('ix_scene_models_model_id'), 'scene_models', ['model_id'], unique=False)
    
    # 3. 重构 model_versions 表
    # 3a. 新增 model_id 和 source 列
    if not _column_exists(op, 'model_versions', 'model_id'):
        op.add_column('model_versions', sa.Column('model_id', sa.Integer(), nullable=True, comment='所属模型'))
    if not _column_exists(op, 'model_versions', 'source'):
        op.add_column('model_versions', sa.Column('source', sa.String(length=20), nullable=True, comment='来源：training/upload/import'))
    
    # 3b. 为现有的 model_versions 创建对应的 Model 记录并回填 model_id
    # 检查是否有需要迁移的数据（model_versions 中有 scene_id 列说明还未迁移）
    needs_model_migration = _column_exists(op, 'model_versions', 'scene_id')
    
    if needs_model_migration:
        # 使用 DISTINCT ON 替代 DISTINCT，因为 JSON 类型无法直接比较
        op.execute("""
            INSERT INTO models (name, description, base_architecture, category, class_names, status, created_at)
            SELECT 
                mv.model_name,
                '从模型版本迁移创建',
                mv.model_type,
                ds.category,
                ds.class_names,
                'active',
                mv.created_at
            FROM (
                SELECT DISTINCT ON (mv.model_name, mv.model_type, ds.category)
                    mv.model_name,
                    mv.model_type,
                    ds.category,
                    ds.class_names,
                    mv.created_at
                FROM model_versions mv
                JOIN detection_scenes ds ON mv.scene_id = ds.id
                ORDER BY mv.model_name, mv.model_type, ds.category, mv.created_at
            ) mv
            JOIN detection_scenes ds ON ds.category = mv.category
        """)
        
        # 回填 model_id（通过 model_name 匹配）
        op.execute("""
            UPDATE model_versions
            SET model_id = (
                SELECT m.id FROM models m
                WHERE m.name = model_versions.model_name
                LIMIT 1
            ),
            source = CASE 
                WHEN training_task_id IS NOT NULL THEN 'training'
                ELSE 'upload'
            END
        """)
    
    # 3c. 删除 scene_id, model_name, model_type 列
    if _column_exists(op, 'model_versions', 'scene_id'):
        op.drop_column('model_versions', 'scene_id')
    if _column_exists(op, 'model_versions', 'model_name'):
        op.drop_column('model_versions', 'model_name')
    if _column_exists(op, 'model_versions', 'model_type'):
        op.drop_column('model_versions', 'model_type')
    
    # 3d. 将 model_id 设为非空（仅在列存在且有数据时）
    if _column_exists(op, 'model_versions', 'model_id'):
        # 先确保没有 NULL 值
        op.execute("DELETE FROM model_versions WHERE model_id IS NULL")
        op.alter_column('model_versions', 'model_id', nullable=False)
    if _column_exists(op, 'model_versions', 'source'):
        op.alter_column('model_versions', 'source', server_default='training')
    
    # 3e. 添加 model_id 索引
    op.create_index(op.f('ix_model_versions_model_id'), 'model_versions', ['model_id'], unique=False, if_not_exists=True)
    
    # 4. 重构 training_tasks 表
    # 4a. 新增 model_id, checkpoint 相关列
    if not _column_exists(op, 'training_tasks', 'model_id'):
        op.add_column('training_tasks', sa.Column('model_id', sa.Integer(), nullable=True, comment='关联模型'))
    if not _column_exists(op, 'training_tasks', 'checkpoint_path'):
        op.add_column('training_tasks', sa.Column('checkpoint_path', sa.String(length=500), nullable=True, comment='checkpoint 文件路径'))
    if not _column_exists(op, 'training_tasks', 'last_checkpoint_epoch'):
        op.add_column('training_tasks', sa.Column('last_checkpoint_epoch', sa.Integer(), nullable=True, server_default='0', comment='最后保存 checkpoint 的 epoch'))
    if not _column_exists(op, 'training_tasks', 'set_as_default'):
        op.add_column('training_tasks', sa.Column('set_as_default', sa.Boolean(), nullable=True, server_default=sa.text('false'), comment='训练完成后是否自动设为默认版本'))
    
    # 4b. 添加 base_architecture 列（替代 model_name）
    needs_training_migration = _column_exists(op, 'training_tasks', 'scene_id')
    
    if not _column_exists(op, 'training_tasks', 'base_architecture'):
        op.add_column('training_tasks', sa.Column('base_architecture', sa.String(length=50), nullable=True, comment='基础架构'))
    
    # 回填 base_architecture
    if needs_training_migration:
        op.execute("""
            UPDATE training_tasks SET base_architecture = model_name
        """)
    
    # 删除旧的 model_name 列
    if _column_exists(op, 'training_tasks', 'model_name'):
        op.drop_column('training_tasks', 'model_name')
    
    # 4c. 为现有的 training_tasks 创建对应的 Model 记录并回填 model_id
    if needs_training_migration:
        # 查找还没有对应 Model 的 training_tasks
        # 注意：PostgreSQL 不支持 INSERT OR IGNORE，使用 NOT EXISTS 替代
        op.execute("""
            INSERT INTO models (name, description, base_architecture, category, class_names, status, created_at)
            SELECT 
                '训练模型_' || tt.id,
                '从训练任务迁移创建',
                tt.base_architecture,
                ds.category,
                ds.class_names,
                'active',
                tt.created_at
            FROM training_tasks tt
            JOIN detection_scenes ds ON tt.scene_id = ds.id
            WHERE NOT EXISTS (
                SELECT 1 FROM models m 
                WHERE m.base_architecture = tt.base_architecture 
                AND m.category = ds.category
            )
            AND NOT EXISTS (
                SELECT 1 FROM models m2
                WHERE m2.name = '训练模型_' || tt.id
            )
        """)
        
        # 回填 model_id
        op.execute("""
            UPDATE training_tasks
            SET model_id = (
                SELECT m.id FROM models m
                JOIN detection_scenes ds ON ds.category = m.category
                WHERE ds.id = training_tasks.scene_id
                AND m.base_architecture = training_tasks.base_architecture
                LIMIT 1
            )
        """)
        
        # 对于还没有 model_id 的 training_tasks，创建一个默认模型
        op.execute("""
            INSERT INTO models (name, description, base_architecture, category, class_names, status, created_at)
            SELECT 
                '默认模型_' || tt.id,
                '自动创建',
                tt.base_architecture,
                'general',
                '[]',
                'active',
                tt.created_at
            FROM training_tasks tt
            WHERE tt.model_id IS NULL
        """)
        
        op.execute("""
            UPDATE training_tasks
            SET model_id = (
                SELECT m.id FROM models m
                WHERE m.name = '默认模型_' || training_tasks.id
            )
            WHERE model_id IS NULL
        """)
    
    # 4d. 删除 scene_id 列，将 model_id 设为非空
    if _column_exists(op, 'training_tasks', 'scene_id'):
        op.drop_column('training_tasks', 'scene_id')
    if _column_exists(op, 'training_tasks', 'model_id'):
        # 先确保没有 NULL 值
        op.execute("DELETE FROM training_tasks WHERE model_id IS NULL")
        op.alter_column('training_tasks', 'model_id', nullable=False)
    
    # 4e. 添加 model_id 索引
    op.create_index(op.f('ix_training_tasks_model_id'), 'training_tasks', ['model_id'], unique=False)
    
    # 5. 更新 status 列的注释（添加 paused 状态）
    # PostgreSQL 支持修改列注释
    op.execute("COMMENT ON COLUMN training_tasks.status IS '状态：pending/running/paused/completed/failed/cancelled'")


def downgrade() -> None:
    """Downgrade schema."""
    
    # 5. 恢复 training_tasks.scene_id
    op.add_column('training_tasks', sa.Column('scene_id', sa.Integer(), nullable=True, comment='关联场景'))
    
    # 尝试回填 scene_id（通过关联关系）
    op.execute("""
        UPDATE training_tasks
        SET scene_id = (
            SELECT sm.scene_id FROM scene_models sm
            JOIN models m ON sm.model_id = m.id
            WHERE m.id = training_tasks.model_id
            LIMIT 1
        )
    """)
    
    # 恢复 model_name 列
    op.add_column('training_tasks', sa.Column('model_name', sa.String(length=50), nullable=True, comment='基础模型'))
    op.execute("UPDATE training_tasks SET model_name = base_architecture")
    
    # 删除新增列
    op.drop_index(op.f('ix_training_tasks_model_id'), 'training_tasks')
    op.drop_column('training_tasks', 'model_id')
    op.drop_column('training_tasks', 'checkpoint_path')
    op.drop_column('training_tasks', 'last_checkpoint_epoch')
    op.drop_column('training_tasks', 'set_as_default')
    op.drop_column('training_tasks', 'base_architecture')
    
    # 4. 恢复 model_versions.scene_id
    op.add_column('model_versions', sa.Column('scene_id', sa.Integer(), nullable=True, comment='所属场景'))
    op.add_column('model_versions', sa.Column('model_name', sa.String(length=100), nullable=True, comment='模型名称'))
    op.add_column('model_versions', sa.Column('model_type', sa.String(length=50), nullable=True, comment='模型类型'))
    
    # 回填
    op.execute("""
        UPDATE model_versions
        SET scene_id = (
            SELECT sm.scene_id FROM scene_models sm
            WHERE sm.model_id = model_versions.model_id
            LIMIT 1
        ),
        model_name = (SELECT m.name FROM models m WHERE m.id = model_versions.model_id),
        model_type = (SELECT m.base_architecture FROM models m WHERE m.id = model_versions.model_id)
    """)
    
    op.drop_index(op.f('ix_model_versions_model_id'), 'model_versions')
    op.drop_column('model_versions', 'model_id')
    op.drop_column('model_versions', 'source')
    
    # 3. 删除 scene_models 表
    op.drop_index(op.f('ix_scene_models_model_id'), 'scene_models')
    op.drop_index(op.f('ix_scene_models_scene_id'), 'scene_models')
    op.drop_table('scene_models')
    
    # 2. 删除 models 表
    op.drop_index(op.f('ix_models_id'), 'models')
    op.drop_table('models')
