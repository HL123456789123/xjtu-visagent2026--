"""食物识别记录支持多张图片。

Revision ID: c3d6e8f4a2b1
Revises: b4d91f0c2a7e
Create Date: 2026-07-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3d6e8f4a2b1"
down_revision: Union[str, Sequence[str], None] = "b4d91f0c2a7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_grouped_raw_detections(
    image_object_name: str, raw_detections: object
) -> list[dict[str, object]]:
    """将单图版本保存的候选项转换成按图片分组的模型原始结果。"""
    detections: list[dict[str, object]] = []
    if isinstance(raw_detections, list):
        for item in raw_detections:
            if not isinstance(item, dict):
                continue
            if {"class_name", "confidence", "bbox"}.issubset(item):
                detections.append(
                    {
                        "class_name": item["class_name"],
                        "confidence": item["confidence"],
                        "bbox": item["bbox"],
                    }
                )
    return [
        {
            "image_index": 0,
            "image_object_name": image_object_name,
            "detections": detections,
        }
    ]


def _to_legacy_candidates(raw_detections: object) -> list[dict[str, object]]:
    """降级时恢复旧版本可读取的候选项格式。"""
    candidates: list[dict[str, object]] = []
    if not isinstance(raw_detections, list):
        return candidates
    for group in raw_detections:
        if not isinstance(group, dict):
            continue
        for detection in group.get("detections", []):
            if not isinstance(detection, dict):
                continue
            class_name = detection.get("class_name")
            confidence = detection.get("confidence")
            bbox = detection.get("bbox")
            if class_name is None or confidence is None or bbox is None:
                continue
            candidates.append(
                {
                    "candidate_id": f"det-{len(candidates) + 1}",
                    "class_name": class_name,
                    "display_name": class_name,
                    "confidence": confidence,
                    "bbox": bbox,
                    "source": "model",
                }
            )
    return candidates


def upgrade() -> None:
    with op.batch_alter_table("food_recognition_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "image_object_names",
                sa.JSON(),
                nullable=True,
                comment="按上传顺序保存的 MinIO 对象名",
            )
        )

    bind = op.get_bind()
    tasks = sa.table(
        "food_recognition_tasks",
        sa.column("id", sa.Integer()),
        sa.column("image_object_name", sa.String()),
        sa.column("image_object_names", sa.JSON()),
        sa.column("raw_detections", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(tasks.c.id, tasks.c.image_object_name, tasks.c.raw_detections)
    ).mappings()
    for row in rows:
        image_object_name = row["image_object_name"]
        bind.execute(
            tasks.update()
            .where(tasks.c.id == row["id"])
            .values(
                image_object_names=[image_object_name],
                raw_detections=_to_grouped_raw_detections(image_object_name, row["raw_detections"]),
            )
        )

    with op.batch_alter_table("food_recognition_tasks") as batch_op:
        batch_op.alter_column("image_object_names", existing_type=sa.JSON(), nullable=False)
        batch_op.drop_column("image_object_name")


def downgrade() -> None:
    with op.batch_alter_table("food_recognition_tasks") as batch_op:
        batch_op.add_column(sa.Column("image_object_name", sa.String(length=500), nullable=True))

    bind = op.get_bind()
    tasks = sa.table(
        "food_recognition_tasks",
        sa.column("id", sa.Integer()),
        sa.column("image_object_name", sa.String()),
        sa.column("image_object_names", sa.JSON()),
        sa.column("raw_detections", sa.JSON()),
    )
    rows = bind.execute(
        sa.select(tasks.c.id, tasks.c.image_object_names, tasks.c.raw_detections)
    ).mappings()
    for row in rows:
        object_names = row["image_object_names"] or []
        first_image_object_name = object_names[0] if object_names else ""
        bind.execute(
            tasks.update()
            .where(tasks.c.id == row["id"])
            .values(
                image_object_name=first_image_object_name,
                raw_detections=_to_legacy_candidates(row["raw_detections"]),
            )
        )

    with op.batch_alter_table("food_recognition_tasks") as batch_op:
        batch_op.alter_column(
            "image_object_name", existing_type=sa.String(length=500), nullable=False
        )
        batch_op.drop_column("image_object_names")
