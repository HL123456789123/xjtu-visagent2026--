from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.core.tz import now_cst
from app.entity.db_models import (
    ChatMessage,
    ChatSession,
    FoodRecognitionTask,
    Recipe,
    User,
    UserRole,
)


def _recipe_data(title: str) -> dict:
    return {
        "title": title,
        "summary": "用于历史恢复测试的菜谱。",
        "servings": 2,
        "cooking_time_minutes": 15,
        "difficulty": "简单",
        "ingredients": [{"name": "牛奶", "amount": 1, "unit": "盒", "note": None}],
        "steps": [{"step_no": 1, "description": "混合食材", "duration_minutes": 5}],
        "nutrition": {
            "basis": "per_serving",
            "calories_kcal": 100,
            "protein_g": 4,
            "fat_g": 3,
            "carbohydrates_g": 12,
        },
    }


def _login(client: TestClient, username: str, password: str) -> None:
    client.cookies.clear()
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_history_chat_and_food_dashboard_are_owner_scoped(client, db, seed_rbac):
    owner = User(
        username="history_owner",
        email="history-owner@example.com",
        hashed_password=hash_password("owner-password"),
        is_active=True,
    )
    other = User(
        username="history_other",
        email="history-other@example.com",
        hashed_password=hash_password("other-password"),
        is_active=True,
    )
    db.add_all([owner, other])
    db.flush()
    db.add_all(
        [
            UserRole(user_id=owner.id, role_id=seed_rbac["operator"].id),
            UserRole(user_id=other.id, role_id=seed_rbac["operator"].id),
        ]
    )

    owner_recognition = FoodRecognitionTask(
        user_id=owner.id,
        image_object_names=["food/owner.jpg"],
        status="completed",
        provider="yolo",
        model_version="food-yolo-v1",
        raw_detections=[
            {
                "image_index": 0,
                "detections": [
                    {"class_name": "milk", "confidence": 0.9, "bbox": {}},
                    {"class_name": "banana", "confidence": 0.8, "bbox": {}},
                ],
            }
        ],
        confirmed_ingredients=[
            {"name": "牛奶", "class_name": "milk", "quantity": 1, "unit": "盒", "source": "model"},
            {"name": "香蕉", "class_name": "banana", "quantity": 1, "unit": "根", "source": "model"},
        ],
        created_at=now_cst(),
    )
    other_recognition = FoodRecognitionTask(
        user_id=other.id,
        image_object_names=["food/other.jpg"],
        status="completed",
        provider="mock",
        model_version="food-mock-v1",
        raw_detections=[],
        confirmed_ingredients=[],
        created_at=now_cst(),
    )
    db.add_all([owner_recognition, other_recognition])
    db.flush()

    owner_recipe = Recipe(
        user_id=owner.id,
        recognition_id=owner_recognition.id,
        version=2,
        recipe_data=_recipe_data("牛奶香蕉饮"),
        generator={"provider": "fake", "model": "fixture-v1", "is_mock": True},
    )
    other_recipe = Recipe(
        user_id=other.id,
        recognition_id=other_recognition.id,
        version=1,
        recipe_data=_recipe_data("其他用户菜谱"),
        generator={"provider": "fake", "model": "fixture-v1", "is_mock": True},
    )
    db.add_all([owner_recipe, other_recipe])
    db.flush()

    owner_session = ChatSession(
        user_id=owner.id,
        recipe_id=owner_recipe.id,
        session_uuid=str(uuid4()),
        title="恢复用会话",
        status="active",
        message_count=2,
        last_message_at=now_cst(),
    )
    db.add(owner_session)
    db.flush()
    db.add_all(
        [
            ChatMessage(session_id=owner_session.id, role="user", content="旧问题"),
            ChatMessage(session_id=owner_session.id, role="assistant", content="旧回答"),
        ]
    )
    db.commit()

    _login(client, "history_owner", "owner-password")
    history = client.get("/api/recipes/history")
    assert history.status_code == 200
    payload = history.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["recipe_id"] == owner_recipe.id
    assert payload["items"][0]["latest_session"]["session_id"] == owner_session.id
    assert payload["items"][0]["confirmed_ingredients"][0]["name"] == "牛奶"

    sessions = client.get(f"/api/chat/sessions?recipe_id={owner_recipe.id}")
    messages = client.get(f"/api/chat/sessions/{owner_session.id}/messages")
    assert sessions.status_code == 200
    assert [item["session_id"] for item in sessions.json()["data"]] == [owner_session.id]
    assert messages.status_code == 200
    assert [item["content"] for item in messages.json()["data"]] == ["旧问题", "旧回答"]

    dashboard = client.get("/api/dashboard/food-stats")
    assert dashboard.status_code == 200
    overview = dashboard.json()["data"]["overview"]
    assert overview == {
        "recognitions": 1,
        "detected_items": 2,
        "confirmed_ingredients": 2,
        "recipes": 1,
        "chat_sessions": 1,
    }
    assert len(dashboard.json()["data"]["trend"]) == 7
    assert dashboard.json()["data"]["ingredient_distribution"] == [
        {"name": "牛奶", "count": 1},
        {"name": "香蕉", "count": 1},
    ]

    _login(client, "history_other", "other-password")
    assert client.get("/api/recipes/history").json()["data"]["total"] == 1
    assert client.get(f"/api/recipes/{owner_recipe.id}").status_code == 403
    assert client.get(f"/api/chat/sessions/{owner_session.id}/messages").status_code == 403
    assert client.get(f"/api/chat/sessions?recipe_id={owner_recipe.id}").status_code == 403


def test_food_model_status_does_not_expose_runtime_paths(client, db, seed_rbac):
    user = User(
        username="model_status_user",
        email="model-status@example.com",
        hashed_password=hash_password("model-password"),
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=seed_rbac["operator"].id))
    db.commit()

    _login(client, "model_status_user", "model-password")
    response = client.get("/api/food/model-status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"provider", "model_version", "available", "class_count", "classes"}
    assert data["class_count"] == len(data["classes"])
    assert "path" not in str(data).lower()
