import json
import re
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ALLOWED_EVENTS = {"token", "recipe_updated", "done", "error"}


def parse_sse_fixture(name: str) -> list[tuple[str, dict]]:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8").strip()
    events = []
    for block in raw.split("\n\n"):
        lines = block.splitlines()
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        events.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def read_backend_file(relative_path: str) -> str:
    path = BACKEND_DIR / relative_path
    assert path.exists(), f"V1 requires backend/{relative_path}, but it is missing"
    return path.read_text(encoding="utf-8")


def assert_regex(text: str, pattern: str, message: str) -> None:
    assert re.search(pattern, text, flags=re.MULTILINE | re.DOTALL), message


def test_sse_recipe_update_fixture_matches_v1_contract():
    events = parse_sse_fixture("sse_recipe_update.txt")
    event_names = [name for name, _payload in events]

    assert event_names == ["token", "recipe_updated", "done"]
    assert set(event_names) <= ALLOWED_EVENTS
    assert events[0][1] == {"content": "已经调整为三人份，并减少了食用油用量。"}
    assert events[1][1] == {"recipe_id": 101, "version": 2}
    assert type(events[1][1]["recipe_id"]) is int
    assert type(events[1][1]["version"]) is int
    assert events[2][1] == {"message_id": 9001}
    assert type(events[2][1]["message_id"]) is int


def test_v1_chat_session_api_uses_recipe_session_contract():
    api_source = read_backend_file("app/api/chat.py")
    schema_source = read_backend_file("app/entity/schemas.py")

    assert_regex(
        api_source,
        r"@router\.post\(\s*['\"]/?sessions['\"]",
        "Chat API must expose POST /api/chat/sessions",
    )
    assert "recipe_id" in api_source + schema_source
    assert "会话创建成功" in api_source
    assert "code=201" in api_source or "status_code=201" in api_source
    assert "session_id" in api_source
    assert "created_at" in api_source


def test_v1_chat_message_api_uses_content_and_event_stream():
    api_source = read_backend_file("app/api/chat.py")
    schema_source = read_backend_file("app/entity/schemas.py")

    assert_regex(
        api_source,
        r"@router\.post\(\s*['\"]/?sessions/\{session_id\}/messages['\"]",
        "Chat API must expose POST /api/chat/sessions/{session_id}/messages",
    )
    assert "text/event-stream" in api_source
    assert "content" in api_source + schema_source
    assert "body.content" in api_source or ".content" in api_source


def test_v1_chat_sse_only_emits_four_allowed_named_events():
    api_source = read_backend_file("app/api/chat.py")
    service_source = read_backend_file("app/services/chat_service.py")
    combined_source = api_source + service_source

    for event_name in ALLOWED_EVENTS:
        assert f"event: {event_name}" in combined_source, f"SSE must emit event: {event_name}"
    assert "event: tool_call" not in combined_source
    assert "event: tool_result" not in combined_source
    assert '"type": "tool_call"' not in combined_source
    assert '"type": "tool_result"' not in combined_source


def test_v1_chat_api_requires_login_and_session_user_isolation():
    api_source = read_backend_file("app/api/chat.py")
    model_source = read_backend_file("app/entity/db_models.py")

    assert "get_current_user" in api_source
    assert "current_user" in api_source
    assert "ChatSession.user_id == current_user.id" in api_source
    assert "recipe_id" in model_source, "chat_sessions must bind each V1 session to a recipe_id"
