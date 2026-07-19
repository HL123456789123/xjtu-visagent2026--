from app.services.agent_prompts import (
    CHAT_SYSTEM_PROMPT,
    RECIPE_GENERATION_SYSTEM_PROMPT,
    RECIPE_JSON_CONTRACT,
)


def test_recipe_prompt_declares_the_complete_json_contract():
    for field in (
        '"title"',
        '"summary"',
        '"servings"',
        '"cooking_time_minutes"',
        '"ingredients"',
        '"steps"',
        '"nutrition"',
        '"per_serving"',
    ):
        assert field in RECIPE_JSON_CONTRACT
        assert field in RECIPE_GENERATION_SYSTEM_PROMPT


def test_chat_prompt_reuses_the_recipe_json_contract_for_updates():
    assert RECIPE_JSON_CONTRACT in CHAT_SYSTEM_PROMPT
    assert '"action": "answer"' in CHAT_SYSTEM_PROMPT
    assert '"action": "update_recipe"' in CHAT_SYSTEM_PROMPT
