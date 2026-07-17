from datetime import datetime
from types import SimpleNamespace

import pytest

import app.services.agent_graph as agent_graph_module
import app.services.recipe_service as recipe_service_module
from app.core.exceptions import PermissionDeniedError, RecipeGenerationError, RecipeNotFoundError
from app.entity.recipe_schema import RecipeCreateRequest
from app.services.llm_gateway import InvalidLLMOutputError, LLMGateway, LLMUnavailableError
from app.services.recipe_service import RecipeService


class FakeRecipeRepository:
    def __init__(self, ingredients=None):
        self.ingredients = ingredients if ingredients is not None else [
            {"name": "番茄", "class_name": "tomato", "quantity": 2, "unit": "个", "source": "model"}
        ]
        self.records = {}
        self.recognition = SimpleNamespace(id=12, user_id=1)

    def get_recognition_for_user(self, db, recognition_id, user_id):
        return self.recognition if recognition_id == 12 and user_id == 1 else None

    def get_confirmed_ingredients(self, db, recognition_id, user_id):
        return self.ingredients

    def create_recipe(self, db, user_id, recognition_id, recipe_data, generator):
        now = datetime.now().astimezone()
        record = SimpleNamespace(
            id=1, user_id=user_id, recognition_id=recognition_id, version=1,
            recipe_data=recipe_data, generator=generator, created_at=now, updated_at=now,
        )
        self.records[1] = record
        return record

    def get_recipe(self, db, recipe_id):
        return self.records.get(recipe_id)

    def save_new_recipe_version(self, db, recipe_id, user_id, recipe_data):
        record = self.records.get(recipe_id)
        if not record or record.user_id != user_id:
            return None
        record.recipe_data = recipe_data
        record.version += 1
        record.updated_at = datetime.now().astimezone()
        return record


@pytest.fixture
def fake_gateway(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.mode = "fake"
    gateway.model = "fixture-v1"
    gateway.client = None
    monkeypatch.setattr(agent_graph_module, "get_llm_gateway", lambda: gateway)
    monkeypatch.setattr(recipe_service_module, "get_llm_gateway", lambda: gateway)
    return gateway


@pytest.mark.asyncio
async def test_create_query_and_update_recipe(fake_gateway):
    repository = FakeRecipeRepository()
    service = RecipeService(repository)
    created = await service.create_recipe(None, RecipeCreateRequest(recognition_id=12), 1)
    assert created.version == 1
    assert created.generator.is_mock is True

    queried = await service.get_recipe(None, created.recipe_id, 1)
    payload = queried.model_dump(exclude={
        "recipe_id", "recognition_id", "version", "nutrition_disclaimer",
        "generator", "created_at", "updated_at",
    })
    payload["servings"] = 3
    updated = await service.update_recipe(None, created.recipe_id, 1, payload)
    assert updated.version == 2
    assert updated.servings == 3


@pytest.mark.asyncio
async def test_unconfirmed_ingredients_is_422(fake_gateway):
    service = RecipeService(FakeRecipeRepository(ingredients=[]))
    with pytest.raises(RecipeGenerationError) as exc:
        await service.create_recipe(None, RecipeCreateRequest(recognition_id=12), 1)
    assert exc.value.error_code == "NO_CONFIRMED_INGREDIENTS"


@pytest.mark.asyncio
async def test_llm_unavailable_is_503(monkeypatch):
    class BrokenGateway:
        async def generate_recipe(self, *args, **kwargs):
            raise LLMUnavailableError("offline")

    monkeypatch.setattr(agent_graph_module, "get_llm_gateway", lambda: BrokenGateway())
    service = RecipeService(FakeRecipeRepository())
    with pytest.raises(RecipeGenerationError) as exc:
        await service.create_recipe(None, RecipeCreateRequest(recognition_id=12), 1)
    assert exc.value.error_code == "LLM_UNAVAILABLE"


def test_real_mode_without_key_is_unavailable(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "LLM_MODE", "real")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(LLMUnavailableError):
        LLMGateway()


@pytest.mark.asyncio
async def test_invalid_llm_output_is_422(monkeypatch):
    class InvalidGateway:
        async def generate_recipe(self, *args, **kwargs):
            raise InvalidLLMOutputError("bad json")

    monkeypatch.setattr(agent_graph_module, "get_llm_gateway", lambda: InvalidGateway())
    service = RecipeService(FakeRecipeRepository())
    with pytest.raises(RecipeGenerationError) as exc:
        await service.create_recipe(None, RecipeCreateRequest(recognition_id=12), 1)
    assert exc.value.error_code == "INVALID_LLM_OUTPUT"


@pytest.mark.asyncio
async def test_not_found_and_permission(fake_gateway):
    repository = FakeRecipeRepository()
    service = RecipeService(repository)
    with pytest.raises(RecipeNotFoundError):
        await service.get_recipe(None, 99, 1)
    await service.create_recipe(None, RecipeCreateRequest(recognition_id=12), 1)
    with pytest.raises(PermissionDeniedError):
        await service.get_recipe(None, 1, 2)
