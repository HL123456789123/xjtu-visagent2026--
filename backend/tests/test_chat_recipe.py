from types import SimpleNamespace

import pytest

import app.services.agent_graph as agent_graph_module
from app.services.chat_service import ChatService
from app.services.llm_gateway import LLMGateway
from tests.test_recipe_service import FakeRecipeRepository
from app.entity.recipe_schema import RecipeCreateRequest
from app.services.recipe_service import RecipeService


class FakeChatRepository:
    def __init__(self):
        self.messages = []

    def create_session(self, db, user_id, recipe_id):
        return SimpleNamespace(id=5, user_id=user_id, recipe_id=recipe_id, created_at=SimpleNamespace(isoformat=lambda: "now"))

    def get_session_for_user(self, db, session_id, user_id):
        if session_id == 5 and user_id == 1:
            return SimpleNamespace(id=5, user_id=1, recipe_id=1)
        return None

    def save_message(self, db, session_id, role, content):
        message = SimpleNamespace(id=len(self.messages) + 1, role=role, content=content)
        self.messages.append(message)
        return message


@pytest.fixture
def gateway(monkeypatch):
    instance = LLMGateway.__new__(LLMGateway)
    instance.mode = "fake"
    instance.model = "fixture-v1"
    instance.client = None
    monkeypatch.setattr(agent_graph_module, "get_llm_gateway", lambda: instance)
    return instance


async def collect(stream):
    return "".join([item async for item in stream])


@pytest.mark.asyncio
async def test_answer_does_not_update_version(gateway):
    recipes = RecipeService(FakeRecipeRepository())
    await recipes.create_recipe(RecipeCreateRequest(recognition_id=12), 1)
    chat = ChatService(FakeChatRepository(), recipes)
    output = await collect(chat.send_message_stream(None, 5, 1, "什么时候出锅？"))
    assert "event: token" in output
    assert "event: done" in output
    assert "event: recipe_updated" not in output
    assert (await recipes.get_recipe(1, 1)).version == 1


@pytest.mark.asyncio
async def test_update_increments_version_and_emits_only_v1_events(gateway):
    recipes = RecipeService(FakeRecipeRepository())
    await recipes.create_recipe(RecipeCreateRequest(recognition_id=12), 1)
    chat = ChatService(FakeChatRepository(), recipes)
    output = await collect(chat.send_message_stream(None, 5, 1, "改成三人份并少放油"))
    assert "event: token" in output
    assert "event: recipe_updated" in output
    assert "event: done" in output
    assert "tool_call" not in output and "tool_result" not in output
    assert (await recipes.get_recipe(1, 1)).version == 2
