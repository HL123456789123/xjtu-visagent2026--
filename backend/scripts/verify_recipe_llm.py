"""Day 4 真实 LLM 冒烟验证；不会输出或保存 API Key。"""

import asyncio
import json

from app.config.settings import settings
from app.services.agent_prompts import CHAT_SYSTEM_PROMPT, RECIPE_GENERATION_SYSTEM_PROMPT
from app.services.llm_gateway import LLMGateway


async def main():
    settings.LLM_MODE = "real"
    gateway = LLMGateway()
    ingredients = [
        {"name": "番茄", "class_name": "tomato", "quantity": 2, "unit": "个", "source": "model"},
        {"name": "鸡蛋", "class_name": "egg", "quantity": 3, "unit": "个", "source": "manual"},
    ]
    preferences = {
        "servings": 2,
        "taste": "清淡",
        "max_time_minutes": 30,
        "avoid_ingredients": [],
    }
    recipe = await gateway.generate_recipe(
        RECIPE_GENERATION_SYSTEM_PROMPT,
        "请使用番茄和鸡蛋生成两人份、30 分钟内完成的清淡菜谱，并严格返回 JSON。",
        ingredients,
        preferences,
    )
    chat = await gateway.chat(
        CHAT_SYSTEM_PROMPT,
        f"当前菜谱：{recipe.model_dump_json()}\n用户消息：改成三人份并少放油",
        recipe.model_dump(),
    )
    print(json.dumps({
        "generator": gateway.generator,
        "recipe_title": recipe.title,
        "recipe_servings": recipe.servings,
        "chat_action": chat.action,
        "updated_servings": chat.recipe.servings if chat.recipe else None,
    }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
