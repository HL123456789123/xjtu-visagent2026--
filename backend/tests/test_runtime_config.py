"""V1.1 runtime configuration and Redis protocol compatibility tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.services import food_recognition_service, llm_gateway
from app.storage import redis_client as redis_client_module


def _write_env(tmp_path: Path, values: list[str]) -> Path:
    env_file = tmp_path / "runtime.env"
    env_file.write_text("\n".join(values) + "\n", encoding="utf-8")
    return env_file


def _v1_runtime_values() -> list[str]:
    return [
        "JWT_SECRET_KEY=runtime-test-secret",
        "FOOD_PROVIDER=mock",
        "FOOD_MODEL_PATH=/tmp/food-model.pt",
        "FOOD_CLASSES_PATH=/tmp/classes.yaml",
        "FOOD_CONF_THRESHOLD=0.42",
        "LLM_MODE=real",
        "LLM_BASE_URL=https://llm.example.test/v1",
        "LLM_API_KEY=placeholder-for-test-only",
        "LLM_MODEL=fixture-model",
        "LLM_TIMEOUT_SECONDS=17.5",
    ]


def test_settings_loads_all_v1_runtime_values_from_env_file(tmp_path: Path):
    settings = Settings(_env_file=_write_env(tmp_path, _v1_runtime_values()))

    assert settings.FOOD_PROVIDER == "mock"
    assert settings.FOOD_MODEL_PATH == "/tmp/food-model.pt"
    assert settings.FOOD_CLASSES_PATH == "/tmp/classes.yaml"
    assert settings.FOOD_CONF_THRESHOLD == 0.42
    assert settings.LLM_MODE == "real"
    assert settings.LLM_BASE_URL == "https://llm.example.test/v1"
    assert settings.LLM_MODEL == "fixture-model"
    assert settings.LLM_TIMEOUT_SECONDS == 17.5


def test_process_environment_overrides_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = _write_env(tmp_path, _v1_runtime_values())
    monkeypatch.setenv("FOOD_PROVIDER", "yolo")
    monkeypatch.setenv("LLM_MODE", "fake")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "31")

    settings = Settings(_env_file=env_file)

    assert settings.FOOD_PROVIDER == "yolo"
    assert settings.LLM_MODE == "fake"
    assert settings.LLM_TIMEOUT_SECONDS == 31


def test_unknown_runtime_variable_in_env_file_is_rejected(tmp_path: Path):
    env_file = _write_env(tmp_path, [*_v1_runtime_values(), "FOOD_PROVIDRE=mock"])

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=env_file)

    assert "food_providre" in str(exc_info.value)
    assert "extra_forbidden" in str(exc_info.value)


def test_llm_gateway_uses_explicit_v1_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = _write_env(
        tmp_path,
        [
            "JWT_SECRET_KEY=runtime-test-secret",
            "LLM_MODE=fake",
            "LLM_BASE_URL=",
            "LLM_API_KEY=",
            "LLM_MODEL=",
            "LLM_TIMEOUT_SECONDS=60",
        ],
    )
    monkeypatch.setattr(llm_gateway, "Settings", lambda: Settings(_env_file=env_file))

    gateway = llm_gateway.LLMGateway()

    assert gateway.generator == {
        "provider": "fake",
        "model": "fixture-v1",
        "is_mock": True,
    }


def test_food_provider_uses_explicit_v1_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env_file = _write_env(
        tmp_path,
        [
            "JWT_SECRET_KEY=runtime-test-secret",
            "FOOD_PROVIDER=mock",
            "FOOD_MODEL_PATH=/tmp/food-model.pt",
            "FOOD_CLASSES_PATH=/tmp/classes.yaml",
            "FOOD_CONF_THRESHOLD=0.25",
        ],
    )
    monkeypatch.setattr(
        food_recognition_service, "Settings", lambda: Settings(_env_file=env_file)
    )
    food_recognition_service.build_default_food_provider.cache_clear()

    provider, provider_name, model_version, display_names = (
        food_recognition_service.build_default_food_provider()
    )

    assert isinstance(provider, food_recognition_service.MockFoodRecognitionProvider)
    assert provider_name == "mock"
    assert model_version == "food-mock-v1"
    assert display_names == {}
    food_recognition_service.build_default_food_provider.cache_clear()


def test_redis_client_explicitly_uses_resp2(monkeypatch: pytest.MonkeyPatch):
    calls: dict[str, object] = {}

    class FakeRedis:
        def ping(self) -> bool:
            return True

    def fake_from_url(*args, **kwargs):
        calls["args"] = args
        calls["kwargs"] = kwargs
        return FakeRedis()

    monkeypatch.setattr(redis_client_module.redis, "from_url", fake_from_url)

    client = redis_client_module.RedisClient()

    assert client.is_connected() is True
    assert calls["kwargs"] == {
        "decode_responses": True,
        "protocol": 2,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
    }
