from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.chat as chat_api
import app.api.recipes as recipe_api
from app.core.exceptions import RecipeGenerationError
from app.core.security import get_current_user
from app.database.session import get_db
from app.entity.recipe_schema import RecipeResponse


def recipe_response():
    now = datetime.now().astimezone()
    return RecipeResponse.model_validate({
        "recipe_id": 1,
        "recognition_id": 12,
        "version": 1,
        "title": "番茄炒蛋",
        "summary": "家常快手菜",
        "servings": 2,
        "cooking_time_minutes": 20,
        "difficulty": "简单",
        "ingredients": [{"name": "番茄", "amount": 2, "unit": "个", "note": None}],
        "steps": [{"step_no": 1, "description": "洗净切块", "duration_minutes": 5}],
        "nutrition": {
            "basis": "per_serving", "calories_kcal": 280, "protein_g": 16.5,
            "fat_g": 15.2, "carbohydrates_g": 18.4,
        },
        "nutrition_disclaimer": "仅供参考",
        "generator": {"provider": "fake", "model": "fixture-v1", "is_mock": True},
        "created_at": now,
        "updated_at": now,
    })


def make_client(*, recipe_service=None, chat_service=None):
    app = FastAPI()
    app.include_router(recipe_api.router)
    app.include_router(chat_api.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)
    if recipe_service is not None:
        app.dependency_overrides[recipe_api.get_recipe_service] = lambda: recipe_service
    if chat_service is not None:
        app.dependency_overrides[chat_api.get_chat_service] = lambda: chat_service
    return TestClient(app)


def test_recipe_create_and_query_contract():
    class Service:
        async def create_recipe(self, body, user_id):
            return recipe_response()

        async def get_recipe(self, recipe_id, user_id):
            return recipe_response()

    with make_client(recipe_service=Service()) as client:
        created = client.post("/api/recipes", json={"recognition_id": 12})
        queried = client.get("/api/recipes/1")
    assert created.status_code == 201
    assert created.json()["data"]["version"] == 1
    assert queried.status_code == 200
    assert queried.json()["data"]["title"] == "番茄炒蛋"


def test_recipe_error_uses_v1_envelope():
    class Service:
        async def create_recipe(self, body, user_id):
            raise RecipeGenerationError("尚未确认食材", code="NO_CONFIRMED_INGREDIENTS")

    with make_client(recipe_service=Service()) as client:
        response = client.post("/api/recipes", json={"recognition_id": 12})
    assert response.status_code == 422
    assert response.json() == {"code": 422, "message": "尚未确认食材", "data": None}


def test_chat_session_and_sse_contract():
    class Service:
        async def create_session(self, db, user_id, recipe_id):
            return SimpleNamespace(id=5, recipe_id=recipe_id, created_at=datetime.now().astimezone())

        def get_session(self, db, session_id, user_id):
            return SimpleNamespace(id=session_id, recipe_id=1)

        async def send_message_stream(self, db, session_id, user_id, content):
            yield 'event: token\ndata: {"content":"已调整"}\n\n'
            yield 'event: recipe_updated\ndata: {"recipe_id":1,"version":2}\n\n'
            yield 'event: done\ndata: {"message_id":9}\n\n'

    with make_client(chat_service=Service()) as client:
        session = client.post("/api/chat/sessions", json={"recipe_id": 1})
        message = client.post("/api/chat/sessions/5/messages", json={"content": "少放油"})
    assert session.status_code == 201
    assert set(session.json()["data"]) == {"session_id", "recipe_id", "created_at"}
    assert "event: recipe_updated" in message.text
    assert "tool_call" not in message.text and "tool_result" not in message.text
