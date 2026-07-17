"""OpenAI-compatible V1 gateway; real failures never fall back to Fake."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from functools import lru_cache

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.entity.recipe_schemas import ChatLLMResult, RecipeGenerateResult


class LLMUnavailableError(RuntimeError):
    pass


class InvalidLLMOutputError(ValueError):
    pass


class LLMGateway:
    def __init__(self) -> None:
        self.mode = os.getenv("LLM_MODE", "real").strip().lower()
        self.model = os.getenv("LLM_MODEL", "").strip()
        self.client: AsyncOpenAI | None = None
        if self.mode == "fake":
            self.model = "fixture-v1"
            return
        if self.mode != "real":
            raise LLMUnavailableError("LLM_MODE must be real or fake")

        api_key = os.getenv("LLM_API_KEY", "").strip()
        base_url = os.getenv("LLM_BASE_URL", "").strip()
        if not api_key or not base_url or not self.model:
            raise LLMUnavailableError("real LLM configuration is incomplete")
        try:
            timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
        except (TypeError, ValueError) as exc:
            raise LLMUnavailableError("real LLM configuration is invalid") from exc

    @property
    def generator(self) -> dict:
        if self.mode == "fake":
            return {"provider": "fake", "model": "fixture-v1", "is_mock": True}
        return {"provider": "openai_compatible", "model": self.model, "is_mock": False}

    async def _json_completion(self, system_prompt: str, user_prompt: str) -> dict:
        if self.client is None:
            raise LLMUnavailableError("real LLM client is unavailable")
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
            raise LLMUnavailableError("real LLM request failed") from exc
        try:
            return json.loads(content or "")
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidLLMOutputError("LLM did not return valid JSON") from exc

    async def generate_recipe(
        self,
        system_prompt: str,
        user_prompt: str,
        ingredients: list[dict],
        preferences: dict,
    ) -> RecipeGenerateResult:
        if self.mode == "fake":
            primary = ingredients[0]["name"] if ingredients else "时蔬"
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
                    {"step_no": 2, "description": "将食材烹熟并调味。", "duration_minutes": 10},
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
            raise InvalidLLMOutputError("LLM recipe shape is invalid") from exc

    async def chat(
        self, system_prompt: str, user_prompt: str, current_recipe: dict
    ) -> ChatLLMResult:
        if self.mode == "fake":
            message = user_prompt.rsplit("用户消息：", 1)[-1]
            if any(word in message for word in ("改", "调整", "换成", "少放", "增加", "减少")):
                updated = deepcopy(current_recipe)
                if "三人" in message:
                    updated["servings"] = 3
                if "少放油" in message:
                    updated["nutrition"]["fat_g"] = max(
                        0, updated["nutrition"]["fat_g"] * 0.7
                    )
                raw = {
                    "action": "update_recipe",
                    "answer": "已经按你的要求调整了菜谱。",
                    "recipe": updated,
                }
            else:
                raw = {
                    "action": "answer",
                    "answer": "可以在食材刚熟时出锅，以保持口感。",
                    "recipe": None,
                }
        else:
            raw = await self._json_completion(system_prompt, user_prompt)
        try:
            return ChatLLMResult.model_validate(raw)
        except ValidationError as exc:
            raise InvalidLLMOutputError("LLM chat shape is invalid") from exc


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
