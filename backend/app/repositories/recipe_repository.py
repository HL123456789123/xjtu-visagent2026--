"""Recipe 的 V1 数据访问实现，菜谱正文保持完整 JSON。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.entity.db_models import Recipe, RecipeVersion


class RecipeRepository:
    """供 Recipe Service 直接调用，调用者无需编写 SQLAlchemy 查询。"""

    def __init__(self, db: Session):
        self.db = db

    def create_recipe(
        self,
        user_id: int,
        recognition_id: int,
        recipe_data: dict[str, Any],
        generator: dict[str, Any],
        *,
        created_at: datetime | None = None,
    ) -> Recipe:
        now = created_at or datetime.now().astimezone()
        recipe = Recipe(
            user_id=user_id,
            recognition_id=recognition_id,
            version=1,
            recipe_data=recipe_data,
            generator=generator,
            created_at=now,
            updated_at=now,
        )
        self.db.add(recipe)
        try:
            self.db.flush()
            self._add_snapshot(
                recipe,
                recipe_data,
                change_type="generated",
                change_reason="初次生成菜谱",
                created_at=now,
            )
            self.db.commit()
            self.db.refresh(recipe)
        except Exception:
            self.db.rollback()
            raise
        return recipe

    def get_recipe_for_user(self, recipe_id: int, user_id: int) -> Recipe | None:
        return (
            self.db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user_id).first()
        )

    def get_recipe(self, recipe_id: int) -> Recipe | None:
        """Internal ownership check helper; public services still use the fixed user-scoped API."""
        return self.db.get(Recipe, recipe_id)

    def list_recipes_for_user(
        self, user_id: int, *, page: int, page_size: int
    ) -> tuple[list[Recipe], int]:
        query = self.db.query(Recipe).filter(Recipe.user_id == user_id)
        total = query.with_entities(func.count(Recipe.id)).scalar() or 0
        records = (
            query.order_by(Recipe.updated_at.desc(), Recipe.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return records, total

    def save_new_recipe_version(
        self,
        recipe_id: int,
        user_id: int,
        recipe_data: dict[str, Any],
        *,
        updated_at: datetime | None = None,
        change_type: str = "chat_update",
        change_reason: str | None = None,
        source_message_id: int | None = None,
        source_version: int | None = None,
    ) -> Recipe | None:
        recipe = (
            self.db.query(Recipe)
            .filter(Recipe.id == recipe_id, Recipe.user_id == user_id)
            .with_for_update()
            .first()
        )
        if recipe is None:
            return None
        now = updated_at or datetime.now().astimezone()
        try:
            self._ensure_current_snapshot(recipe)
            recipe.version += 1
            recipe.recipe_data = deepcopy(recipe_data)
            recipe.updated_at = now
            self._add_snapshot(
                recipe,
                recipe_data,
                change_type=change_type,
                change_reason=change_reason,
                source_message_id=source_message_id,
                source_version=source_version,
                created_at=now,
            )
            self.db.commit()
            self.db.refresh(recipe)
        except Exception:
            self.db.rollback()
            raise
        return recipe

    def ensure_current_snapshot(self, recipe_id: int, user_id: int) -> Recipe | None:
        recipe = self.get_recipe_for_user(recipe_id, user_id)
        if recipe is None:
            return None
        try:
            created = self._ensure_current_snapshot(recipe)
            if created:
                self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return recipe

    def list_versions(self, recipe_id: int, user_id: int) -> list[RecipeVersion] | None:
        recipe = self.ensure_current_snapshot(recipe_id, user_id)
        if recipe is None:
            return None
        return (
            self.db.query(RecipeVersion)
            .filter(RecipeVersion.recipe_id == recipe_id)
            .order_by(RecipeVersion.version.desc())
            .all()
        )

    def get_version(
        self, recipe_id: int, version: int, user_id: int
    ) -> RecipeVersion | None:
        recipe = self.ensure_current_snapshot(recipe_id, user_id)
        if recipe is None:
            return None
        return (
            self.db.query(RecipeVersion)
            .filter(
                RecipeVersion.recipe_id == recipe_id,
                RecipeVersion.version == version,
            )
            .first()
        )

    def restore_version(
        self, recipe_id: int, version: int, user_id: int
    ) -> Recipe | None:
        snapshot = self.get_version(recipe_id, version, user_id)
        if snapshot is None:
            return None
        return self.save_new_recipe_version(
            recipe_id,
            user_id,
            snapshot.recipe_data,
            change_type="restore",
            change_reason=f"恢复自 v{version}",
            source_version=version,
        )

    def _ensure_current_snapshot(self, recipe: Recipe) -> bool:
        exists = (
            self.db.query(RecipeVersion.id)
            .filter(
                RecipeVersion.recipe_id == recipe.id,
                RecipeVersion.version == recipe.version,
            )
            .first()
        )
        if exists is not None:
            return False
        self._add_snapshot(
            recipe,
            recipe.recipe_data,
            change_type="backfill",
            change_reason="从现有最新菜谱回填；更早版本不可恢复",
            created_at=recipe.updated_at or recipe.created_at,
        )
        return True

    def _add_snapshot(
        self,
        recipe: Recipe,
        recipe_data: dict[str, Any],
        *,
        change_type: str,
        change_reason: str | None,
        created_at: datetime,
        source_message_id: int | None = None,
        source_version: int | None = None,
    ) -> RecipeVersion:
        snapshot = RecipeVersion(
            recipe_id=recipe.id,
            version=recipe.version,
            recipe_data=deepcopy(recipe_data),
            change_type=change_type,
            change_reason=change_reason,
            source_message_id=source_message_id,
            source_version=source_version,
            created_at=created_at,
        )
        self.db.add(snapshot)
        return snapshot

    def _commit_and_refresh(self, entity: Recipe) -> None:
        try:
            self.db.commit()
            self.db.refresh(entity)
        except Exception:
            self.db.rollback()
            raise
