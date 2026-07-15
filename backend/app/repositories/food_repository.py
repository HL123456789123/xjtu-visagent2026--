"""Food 识别任务的数据访问实现。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.entity.db_models import FoodRecognitionTask


class FoodRepository:
    """封装 V1 Food 识别任务的全部 SQLAlchemy 查询。"""

    def __init__(self, db: Session):
        self.db = db

    def create_recognition(
        self,
        *,
        user_id: int,
        image_object_name: str,
        provider: str,
        model_version: str,
        raw_detections: list[dict[str, Any]],
        created_at: datetime,
    ) -> FoodRecognitionTask:
        task = FoodRecognitionTask(
            user_id=user_id,
            image_object_name=image_object_name,
            status="completed",
            provider=provider,
            model_version=model_version,
            raw_detections=raw_detections,
            confirmed_ingredients=[],
            created_at=created_at,
            updated_at=created_at,
        )
        self.db.add(task)
        self._commit_and_refresh(task)
        return task

    def get_recognition(self, recognition_id: int) -> FoodRecognitionTask | None:
        return self.db.get(FoodRecognitionTask, recognition_id)

    def get_recognition_for_user(
        self, recognition_id: int, user_id: int
    ) -> FoodRecognitionTask | None:
        return (
            self.db.query(FoodRecognitionTask)
            .filter(
                FoodRecognitionTask.id == recognition_id,
                FoodRecognitionTask.user_id == user_id,
            )
            .first()
        )

    def save_raw_detections(
        self, recognition_id: int, detections: list[dict[str, Any]]
    ) -> FoodRecognitionTask | None:
        task = self.get_recognition(recognition_id)
        if task is None:
            return None
        task.raw_detections = detections
        self._commit_and_refresh(task)
        return task

    def replace_confirmed_ingredients(
        self,
        recognition_id: int,
        user_id: int,
        ingredients: list[dict[str, Any]],
        confirmed_at: datetime,
    ) -> FoodRecognitionTask | None:
        task = self.get_recognition_for_user(recognition_id, user_id)
        if task is None:
            return None
        task.confirmed_ingredients = ingredients
        task.updated_at = confirmed_at
        self._commit_and_refresh(task)
        return task

    def get_confirmed_ingredients(
        self, recognition_id: int, user_id: int
    ) -> list[dict[str, Any]] | None:
        task = self.get_recognition_for_user(recognition_id, user_id)
        return None if task is None else list(task.confirmed_ingredients or [])

    def _commit_and_refresh(self, entity: FoodRecognitionTask) -> None:
        try:
            self.db.commit()
            self.db.refresh(entity)
        except Exception:
            self.db.rollback()
            raise
