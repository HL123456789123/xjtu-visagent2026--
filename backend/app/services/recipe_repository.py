"""Recipe/Food 数据访问层。"""

from sqlalchemy.orm import Session

from app.entity.db_models import FoodRecognitionTask, Recipe


class RecipeRepository:
    def get_recognition_for_user(self, db: Session, recognition_id: int, user_id: int):
        return db.query(FoodRecognitionTask).filter(
            FoodRecognitionTask.id == recognition_id,
            FoodRecognitionTask.user_id == user_id,
        ).first()

    def get_confirmed_ingredients(self, db: Session, recognition_id: int, user_id: int) -> list[dict]:
        recognition = self.get_recognition_for_user(db, recognition_id, user_id)
        return list(recognition.confirmed_ingredients or []) if recognition else []

    def create_recipe(
        self, db: Session, user_id: int, recognition_id: int, recipe_data: dict, generator: dict
    ) -> Recipe:
        recipe = Recipe(
            user_id=user_id,
            recognition_id=recognition_id,
            version=1,
            recipe_data=recipe_data,
            generator=generator,
        )
        db.add(recipe)
        db.commit()
        db.refresh(recipe)
        return recipe

    def get_recipe(self, db: Session, recipe_id: int):
        return db.query(Recipe).filter(Recipe.id == recipe_id).first()

    def get_recipe_for_user(self, db: Session, recipe_id: int, user_id: int):
        return db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user_id).first()

    def save_new_recipe_version(
        self, db: Session, recipe_id: int, user_id: int, recipe_data: dict
    ):
        recipe = self.get_recipe_for_user(db, recipe_id, user_id)
        if recipe is None:
            return None
        recipe.recipe_data = recipe_data
        recipe.version += 1
        db.commit()
        db.refresh(recipe)
        return recipe


recipe_repository = RecipeRepository()
