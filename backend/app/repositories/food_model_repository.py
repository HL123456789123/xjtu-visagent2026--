"""Database operations for versioned Food inference packages."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.entity.db_models import FoodModelVersion


class FoodModelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_versions(self) -> list[FoodModelVersion]:
        return (
            self.db.query(FoodModelVersion)
            .order_by(FoodModelVersion.created_at.desc(), FoodModelVersion.id.desc())
            .all()
        )

    def get(self, model_id: int) -> FoodModelVersion | None:
        return self.db.get(FoodModelVersion, model_id)

    def get_by_version(self, version: str) -> FoodModelVersion | None:
        return (
            self.db.query(FoodModelVersion)
            .filter(FoodModelVersion.version == version)
            .first()
        )

    def get_active(self) -> FoodModelVersion | None:
        return (
            self.db.query(FoodModelVersion)
            .filter(FoodModelVersion.is_active.is_(True))
            .first()
        )

    def create(self, **values) -> FoodModelVersion:
        record = FoodModelVersion(**values)
        self.db.add(record)
        self._commit_and_refresh(record)
        return record

    def mark_ready(self, record: FoodModelVersion, validated_at: datetime) -> FoodModelVersion:
        record.status = "ready"
        record.validation_error = None
        record.validated_at = validated_at
        self._commit_and_refresh(record)
        return record

    def mark_failed(self, record: FoodModelVersion, message: str) -> FoodModelVersion:
        record.status = "failed"
        record.validation_error = message[:1000]
        self._commit_and_refresh(record)
        return record

    def activate(
        self, record: FoodModelVersion, *, actor_id: int, activated_at: datetime
    ) -> FoodModelVersion:
        try:
            current = self.get_active()
            if current is not None and current.id != record.id:
                current.is_active = False
                current.status = "ready"
            record.is_active = True
            record.status = "active"
            record.activated_by = actor_id
            record.activated_at = activated_at
            self.db.commit()
            self.db.refresh(record)
            return record
        except Exception:
            self.db.rollback()
            raise

    def get_rollback_candidate(self, active_id: int) -> FoodModelVersion | None:
        return (
            self.db.query(FoodModelVersion)
            .filter(
                FoodModelVersion.id != active_id,
                FoodModelVersion.status == "ready",
            )
            .order_by(
                FoodModelVersion.activated_at.desc().nullslast(),
                FoodModelVersion.validated_at.desc(),
            )
            .first()
        )

    def healthy_count(self) -> int:
        return (
            self.db.query(FoodModelVersion)
            .filter(FoodModelVersion.status.in_(("ready", "active")))
            .count()
        )

    def delete(self, record: FoodModelVersion) -> None:
        try:
            self.db.delete(record)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _commit_and_refresh(self, record: FoodModelVersion) -> None:
        try:
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise
