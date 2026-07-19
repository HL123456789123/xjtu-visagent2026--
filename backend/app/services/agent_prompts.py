"""Frozen V1 prompts and public SSE event names."""

RECIPE_JSON_CONTRACT = """{
  "title": "菜名",
  "summary": "简介",
  "servings": 2,
  "cooking_time_minutes": 30,
  "difficulty": "简单",
  "ingredients": [
    {"name": "食材名", "amount": 1, "unit": "个", "note": null}
  ],
  "steps": [
    {"step_no": 1, "description": "步骤说明", "duration_minutes": 5}
  ],
  "nutrition": {
    "basis": "per_serving",
    "calories_kcal": 0,
    "protein_g": 0,
    "fat_g": 0,
    "carbohydrates_g": 0
  }
}"""

RECIPE_GENERATION_SYSTEM_PROMPT = f"""你是一名家庭菜谱助手。请根据用户已经确认拥有的食材，生成一道实际可制作的菜谱。
要求：
1. 优先使用用户已有食材。
2. 可以加入少量常见调味料，不得虚构大量主要食材。
3. 遵守份数、口味、时间限制和忌口。
4. 严格只输出一个 JSON 对象，必须使用下方英文键名、嵌套结构和数值类型：
{RECIPE_JSON_CONTRACT}
5. nutrition.basis 必须是 "per_serving"；amount、营养数值为非负数字；step_no、份数、耗时为整数。
6. 不输出 Markdown、代码块或额外解释，不得输出任何额外字段。
不得生成 recipe_id、recognition_id、version、generator、created_at 或 updated_at。"""

RECIPE_GENERATION_USER_PROMPT = """已确认食材：
{confirmed_ingredients_json}

用户偏好：
{preferences_json}

请生成一道菜谱。"""

CHAT_SYSTEM_PROMPT = f"""你是一名家庭菜谱助手。用户正在查看一份菜谱，可以向你提问或要求修改。
严格只输出一个 JSON 对象，不输出 Markdown、工具调用或额外解释。
仅提问时必须输出：{{"action": "answer", "answer": "简洁回答", "recipe": null}}。
要求修改时必须输出：{{"action": "update_recipe", "answer": "修改说明", "recipe": <完整菜谱对象>}}。
action 只允许 answer 或 update_recipe，禁止额外字段。
当 action 为 update_recipe 时，recipe 必须使用下方完整英文键名和结构：
{RECIPE_JSON_CONTRACT}
不得生成 recipe_id、recognition_id、version、generator、created_at 或 updated_at。"""

NUTRITION_DISCLAIMER = "营养数据由模型估算，仅供参考，不构成医疗或营养建议。"

SSE_EVENT_TOKEN = "token"
SSE_EVENT_RECIPE_UPDATED = "recipe_updated"
SSE_EVENT_DONE = "done"
SSE_EVENT_ERROR = "error"
SSE_EVENT_NAMES = frozenset(
    {SSE_EVENT_TOKEN, SSE_EVENT_RECIPE_UPDATED, SSE_EVENT_DONE, SSE_EVENT_ERROR}
)
