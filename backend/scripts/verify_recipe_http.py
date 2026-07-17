"""Day 5 HTTP 全链路验证：登录、生成、查询、问答和版本更新。"""

import asyncio
import json
import time

import httpx

from app.database.session import SessionLocal
from app.entity.db_models import FoodRecognitionTask


BASE_URL = "http://127.0.0.1:8888"


async def main():
    username = f"day5_verify_{int(time.time())}"
    password = "Day5Verify!2026"
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180, trust_env=False) as client:
        registered = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        registered.raise_for_status()
        login = await client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        login.raise_for_status()
        login_data = login.json()
        token = login_data["access_token"]
        user_id = login_data["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        with SessionLocal() as db:
            recognition = FoodRecognitionTask(
                user_id=user_id,
                image_object_names=["food/day5/mock.jpg"],
                status="completed",
                provider="mock",
                model_version="fixture-v1",
                raw_detections=[],
                confirmed_ingredients=[
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
                        "source": "manual",
                    },
                ],
            )
            db.add(recognition)
            db.commit()
            db.refresh(recognition)
            recognition_id = recognition.id

        generated = await client.post(
            "/api/recipes",
            headers=headers,
            json={
                "recognition_id": recognition_id,
                "preferences": {
                    "servings": 2,
                    "taste": "清淡",
                    "max_time_minutes": 30,
                    "avoid_ingredients": [],
                },
            },
        )
        generated.raise_for_status()
        recipe = generated.json()["data"]
        recipe_id = recipe["recipe_id"]

        queried = await client.get(f"/api/recipes/{recipe_id}", headers=headers)
        queried.raise_for_status()
        session = await client.post(
            "/api/chat/sessions", headers=headers, json={"recipe_id": recipe_id}
        )
        session.raise_for_status()
        session_id = session.json()["data"]["session_id"]

        answer = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            headers={**headers, "Accept": "text/event-stream"},
            json={"content": "鸡蛋怎样炒得更嫩？"},
        )
        answer.raise_for_status()
        updated = await client.post(
            f"/api/chat/sessions/{session_id}/messages",
            headers={**headers, "Accept": "text/event-stream"},
            json={"content": "改成三人份并少放油"},
        )
        updated.raise_for_status()
        final_recipe = await client.get(f"/api/recipes/{recipe_id}", headers=headers)
        final_recipe.raise_for_status()
        final_data = final_recipe.json()["data"]

        print(json.dumps({
            "recipe_status": generated.status_code,
            "query_status": queried.status_code,
            "generator": recipe["generator"],
            "answer_events": [line[7:] for line in answer.text.splitlines() if line.startswith("event: ")],
            "update_events": [line[7:] for line in updated.text.splitlines() if line.startswith("event: ")],
            "initial_version": recipe["version"],
            "final_version": final_data["version"],
            "final_servings": final_data["servings"],
        }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
