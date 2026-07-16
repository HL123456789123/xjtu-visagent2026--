"""OpenAI-compatible LLM gateway，真实模式失败时绝不回退 Fake。"""

import json
from copy import deepcopy

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config.settings import settings
from app.entity.recipe_schema import ChatLLMResult, RecipeGenerateResult


class LLMUnavailableError(RuntimeError):
    pass


class InvalidLLMOutputError(ValueError):
    pass


class LLMGateway:
    def __init__(self):
        self.mode = settings.LLM_MODE.lower()
        self.model = settings.OPENAI_MODEL
        self.client = None
        if self.mode == "real":
            if not settings.OPENAI_API_KEY:
                raise LLMUnavailableError("未配置 OPENAI_API_KEY")
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )

    @property
    def generator(self) -> dict:
        if self.mode == "fake":
            return {"provider": "fake", "model": "fixture-v1", "is_mock": True}
        return {"provider": "openai_compatible", "model": self.model, "is_mock": False}

    async def _json_completion(self, system_prompt: str, user_prompt: str) -> dict:
        if self.client is None:
            raise LLMUnavailableError("真实 LLM 客户端未初始化")
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            content = response.choices[0].message.content
        except Exception as exc:
            raise LLMUnavailableError(str(exc)) from exc
        try:
            return json.loads(content or "")
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidLLMOutputError("LLM 未返回合法 JSON") from exc

    async def generate_recipe(
        self, system_prompt: str, user_prompt: str, ingredients: list[dict], preferences: dict
    ) -> RecipeGenerateResult:
        if self.mode == "fake":
            names = [item["name"] for item in ingredients]
            primary = names[0] if names else "时蔬"
            raw = {
                "title": f"家常{primary}",
                "summary": "一道简单易做的家常菜。",
                "servings": preferences.get("servings", 2),
                "cooking_time_minutes": min(preferences.get("max_time_minutes") or 20, 20),
                "difficulty": "简单",
                "ingredients": [
                    {
                        "name": item["name"],
                        "amount": item.get("quantity", 1),
                        "unit": item.get("unit", "份"),
                        "note": None,
                    }
                    for item in ingredients
                ],
                "steps": [
                    {"step_no": 1, "description": "清洗并处理全部食材。", "duration_minutes": 5},
                    {"step_no": 2, "description": "热锅后将食材炒熟并调味。", "duration_minutes": 10},
                ],
                "nutrition": {
                    "basis": "per_serving",
                    "calories_kcal": 280,
                    "protein_g": 16.5,
                    "fat_g": 15.2,
                    "carbohydrates_g": 18.4,
                },
            }
        else:
            raw = await self._json_completion(system_prompt, user_prompt)
        try:
            return RecipeGenerateResult.model_validate(raw)
        except ValidationError as exc:
            raise InvalidLLMOutputError("LLM 菜谱结构校验失败") from exc

    async def chat(self, system_prompt: str, user_prompt: str, current_recipe: dict) -> ChatLLMResult:
        if self.mode == "fake":
            message = user_prompt.rsplit("用户消息：", 1)[-1]
            if any(word in message for word in ("改", "调整", "换成", "少放", "增加", "减少")):
                updated = deepcopy(current_recipe)
                updated["servings"] = 3 if "三人" in message else updated["servings"]
                if "少放油" in message:
                    updated["nutrition"]["fat_g"] = max(0, updated["nutrition"]["fat_g"] * 0.7)
                raw = {
                    "action": "update_recipe",
                    "answer": "已经按你的要求调整了菜谱。",
                    "recipe": updated,
                }
            else:
                raw = {"action": "answer", "answer": "可以在食材刚熟时出锅，以保持口感。", "recipe": None}
        else:
            raw = await self._json_completion(system_prompt, user_prompt)
        try:
            return ChatLLMResult.model_validate(raw)
        except ValidationError as exc:
            raise InvalidLLMOutputError("LLM 对话结构校验失败") from exc


_llm_cache: LLMGateway | None = None


def get_llm_gateway() -> LLMGateway:
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMGateway()
    return _llm_cache
