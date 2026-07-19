"""Recipe 的 V1 数据访问实现，菜谱正文保持完整 JSON。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.entity.db_models import Recipe


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
        self._commit_and_refresh(recipe)
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
    ) -> Recipe | None:
        recipe = self.get_recipe_for_user(recipe_id, user_id)
        if recipe is None:
            return None
        recipe.version += 1
        recipe.recipe_data = recipe_data
        recipe.updated_at = updated_at or datetime.now().astimezone()
        self._commit_and_refresh(recipe)
        return recipe

    def _commit_and_refresh(self, entity: Recipe) -> None:
        try:
            self.db.commit()
            self.db.refresh(entity)
        except Exception:
            self.db.rollback()
            raise
