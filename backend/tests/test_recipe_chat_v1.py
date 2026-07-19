from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.session import Base
from app.entity.db_models import User
from app.entity.recipe_schemas import (
    ChatLLMResult,
    CreateChatSessionRequest,
    RecipeCreateRequest,
    RecipeGenerateResult,
    RecipeResponse,
    SendChatMessageRequest,
)
from app.repositories.chat_repository import ChatRepository
from app.repositories.food_repository import FoodRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.agent_graph import chat_recipe_graph, generate_recipe_graph
from app.services.agent_prompts import NUTRITION_DISCLAIMER, SSE_EVENT_NAMES
from app.services.chat_service import ChatService
from app.services.llm_gateway import get_llm_gateway
from app.services.recipe_service import (
    NoConfirmedIngredientsError,
    RecipeLLMUnavailableError,
    RecipePermissionDeniedError,
    RecipeService,
)


@pytest.fixture(autouse=True)
def fake_llm_mode(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "fake")
    get_llm_gateway.cache_clear()
    yield
    get_llm_gateway.cache_clear()


@pytest.fixture
def repositories():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(username="recipe_user", email="recipe@example.com", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        yield db, user, FoodRepository(db), RecipeRepository(db), ChatRepository(db)
    finally:
        db.close()
        engine.dispose()


def create_recognition(food_repository: FoodRepository, user_id: int, *, confirmed: bool = True):
    recognition = food_repository.create_recognition(
        user_id=user_id,
        image_object_names=["food/test.png"],
        status="completed",
        provider="mock",
        model_version="food-mock-v1",
        created_at=datetime.now().astimezone(),
    )
    if confirmed:
        food_repository.replace_confirmed_ingredients(
            recognition.id,
            user_id,
            [
                {
                    "name": "番茄",
                    "class_name": "tomato",
                    "quantity": 2,
                    "unit": "个",
                    "source": "model",
                },
                {
                    "name": "鸡蛋",
                    "class_name": "egg",
                    "quantity": 3,
                    "unit": "个",
                    "source": "model",
                },
            ],
            datetime.now().astimezone(),
        )
    return recognition


@pytest.mark.asyncio
async def test_recipe_generation_uses_confirmed_ingredients_and_backend_owned_fields(repositories):
    _, user, food_repository, recipe_repository, _ = repositories
    recognition = create_recognition(food_repository, user.id)
    service = RecipeService(food_repository, recipe_repository)
    response = await service.create_recipe(
        RecipeCreateRequest(
            recognition_id=recognition.id,
            preferences={
                "servings": 2,
                "taste": "清淡",
                "max_time_minutes": 30,
                "avoid_ingredients": [],
            },
        ),
        user.id,
    )

    assert response.recipe_id == 1
    assert response.recognition_id == recognition.id
    assert response.version == 1
    assert response.cooking_time_minutes == 20
    assert response.nutrition.carbohydrates_g == 18.4
    assert response.nutrition_disclaimer == NUTRITION_DISCLAIMER
    assert response.generator.model_dump() == {
        "provider": "fake",
        "model": "fixture-v1",
        "is_mock": True,
    }
    record = recipe_repository.get_recipe(response.recipe_id)
    assert record is not None
    assert not {
        "recipe_id",
        "recognition_id",
        "version",
        "generator",
        "created_at",
        "updated_at",
    }.intersection(record.recipe_data)


@pytest.mark.asyncio
async def test_recipe_generation_rejects_unconfirmed_recognition(repositories):
    _, user, food_repository, recipe_repository, _ = repositories
    recognition = create_recognition(food_repository, user.id, confirmed=False)
    service = RecipeService(food_repository, recipe_repository)

    with pytest.raises(NoConfirmedIngredientsError) as exc_info:
        await service.create_recipe(RecipeCreateRequest(recognition_id=recognition.id), user.id)
    assert exc_info.value.error_code == "NO_CONFIRMED_INGREDIENTS"


@pytest.mark.asyncio
async def test_real_llm_configuration_failure_does_not_fall_back_to_fake(
    repositories, monkeypatch
):
    _, user, food_repository, recipe_repository, _ = repositories
    recognition = create_recognition(food_repository, user.id)
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    get_llm_gateway.cache_clear()
    service = RecipeService(food_repository, recipe_repository)

    with pytest.raises(RecipeLLMUnavailableError) as exc_info:
        await service.create_recipe(RecipeCreateRequest(recognition_id=recognition.id), user.id)
    assert exc_info.value.error_code == "LLM_UNAVAILABLE"
    assert recipe_repository.get_recipe(1) is None


def event_names(chunks: list[str]) -> list[str]:
    return [chunk.splitlines()[0].removeprefix("event: ") for chunk in chunks]


def event_data(chunk: str) -> dict:
    return json.loads(chunk.splitlines()[1].removeprefix("data: "))


@pytest.mark.asyncio
async def test_chat_answer_does_not_increment_version_and_uses_only_v1_events(repositories):
    _, user, food_repository, recipe_repository, chat_repository = repositories
    recognition = create_recognition(food_repository, user.id)
    recipes = RecipeService(food_repository, recipe_repository)
    recipe = await recipes.create_recipe(
        RecipeCreateRequest(recognition_id=recognition.id), user.id
    )
    chat = ChatService(chat_repository, recipes)
    session = await chat.create_session(user.id, recipe.recipe_id)

    chunks = [
        chunk
        async for chunk in chat.send_message_stream(
            session.id, user.id, "鸡蛋怎么炒得嫩一些？"
        )
    ]

    assert event_names(chunks) == ["token", "done"]
    assert set(event_names(chunks)).issubset(SSE_EVENT_NAMES)
    assert type(event_data(chunks[-1])["message_id"]) is int
    assert recipe_repository.get_recipe(recipe.recipe_id).version == 1


@pytest.mark.asyncio
async def test_chat_update_replaces_complete_recipe_and_increments_once(repositories):
    _, user, food_repository, recipe_repository, chat_repository = repositories
    recognition = create_recognition(food_repository, user.id)
    recipes = RecipeService(food_repository, recipe_repository)
    recipe = await recipes.create_recipe(
        RecipeCreateRequest(recognition_id=recognition.id), user.id
    )
    chat = ChatService(chat_repository, recipes)
    session = await chat.create_session(user.id, recipe.recipe_id)

    chunks = [
        chunk
        async for chunk in chat.send_message_stream(
            session.id, user.id, "改成三人份并且少放油"
        )
    ]

    assert event_names(chunks) == ["token", "recipe_updated", "done"]
    update = event_data(chunks[1])
    assert update == {"recipe_id": recipe.recipe_id, "version": 2}
    updated = recipe_repository.get_recipe(recipe.recipe_id)
    assert updated.version == 2
    assert updated.recipe_data["servings"] == 3
    assert set(updated.recipe_data) == {
        "title",
        "summary",
        "servings",
        "cooking_time_minutes",
        "difficulty",
        "ingredients",
        "steps",
        "nutrition",
    }


@pytest.mark.asyncio
async def test_missing_session_uses_session_not_found_sse(repositories):
    _, user, food_repository, recipe_repository, chat_repository = repositories
    chat = ChatService(chat_repository, RecipeService(food_repository, recipe_repository))
    chunks = [
        chunk async for chunk in chat.send_message_stream(999, user.id, "测试")
    ]
    assert event_names(chunks) == ["error"]
    assert event_data(chunks[0])["code"] == "SESSION_NOT_FOUND"


@pytest.mark.asyncio
async def test_recipe_and_chat_history_are_restored_only_for_the_owner(repositories):
    db, user, food_repository, recipe_repository, chat_repository = repositories
    recognition = create_recognition(food_repository, user.id)
    recipes = RecipeService(food_repository, recipe_repository, chat_repository)
    recipe = await recipes.create_recipe(
        RecipeCreateRequest(recognition_id=recognition.id), user.id
    )
    chat = ChatService(chat_repository, recipes)
    session = await chat.create_session(user.id, recipe.recipe_id)
    chat_repository.save_message(session.id, "user", "请保留这个会话")
    chat_repository.save_message(session.id, "assistant", "历史会话已保存")

    other_user = User(username="other_user", email="other@example.com", hashed_password="x")
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    history = await recipes.list_history(user.id, page=1, page_size=20)
    assert history.total == 1
    assert history.items[0].recipe_id == recipe.recipe_id
    assert history.items[0].recognition_id == recognition.id
    assert history.items[0].confirmed_ingredients[0]["name"]
    assert history.items[0].latest_session is not None
    assert history.items[0].latest_session.session_id == session.id

    sessions = await chat.list_sessions(user.id, recipe.recipe_id)
    messages = chat.list_messages(session.id, user.id)
    assert [item.session_id for item in sessions] == [session.id]
    assert [(item.role, item.content) for item in messages] == [
        ("user", "请保留这个会话"),
        ("assistant", "历史会话已保存"),
    ]

    assert (await recipes.list_history(other_user.id, page=1, page_size=20)).items == []
    with pytest.raises(RecipePermissionDeniedError):
        await chat.list_sessions(other_user.id, recipe.recipe_id)
    with pytest.raises(RecipePermissionDeniedError):
        chat.list_messages(session.id, other_user.id)


def test_request_and_llm_schemas_forbid_extra_or_backend_owned_fields():
    with pytest.raises(ValidationError):
        RecipeCreateRequest.model_validate(
            {"recognition_id": 1, "preferences": {}, "legacy_mode": True}
        )
    with pytest.raises(ValidationError):
        CreateChatSessionRequest.model_validate({"recipe_id": 1, "content": "extra"})
    with pytest.raises(ValidationError):
        SendChatMessageRequest.model_validate({"content": "hello", "recipe_id": 1})
    with pytest.raises(ValidationError):
        RecipeGenerateResult.model_validate(
            {
                "recipe_id": 99,
                "title": "非法",
                "summary": "LLM 不得生成 ID",
                "servings": 2,
                "cooking_time_minutes": 10,
                "difficulty": "简单",
                "ingredients": [{"name": "番茄", "amount": 1, "unit": "个"}],
                "steps": [{"step_no": 1, "description": "烹饪"}],
                "nutrition": {
                    "basis": "per_serving",
                    "calories_kcal": 1,
                    "protein_g": 1,
                    "fat_g": 1,
                    "carbohydrates_g": 1,
                },
            }
        )
    with pytest.raises(ValidationError):
        ChatLLMResult.model_validate(
            {"action": "tool_call", "answer": "bad", "recipe": None}
        )


def test_canonical_recipe_fixture_matches_strict_response_schema():
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "recipe_success.json").read_text(
            encoding="utf-8"
        )
    )
    parsed = RecipeResponse.model_validate(payload["data"])
    assert type(parsed.recipe_id) is int
    assert parsed.nutrition_disclaimer == NUTRITION_DISCLAIMER


def test_graphs_keep_only_the_two_minimal_v1_flows():
    generate_nodes = set(generate_recipe_graph.get_graph().nodes)
    chat_nodes = set(chat_recipe_graph.get_graph().nodes)
    assert generate_nodes == {
        "__start__",
        "load_confirmed_ingredients",
        "generate_recipe",
        "validate_and_save",
        "__end__",
    }
    assert chat_nodes == {
        "__start__",
        "load_recipe_context",
        "call_llm",
        "answer",
        "update_recipe",
        "__end__",
    }
