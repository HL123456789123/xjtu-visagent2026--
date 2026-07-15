import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
ALLOWED_EVENTS = {"token", "recipe_updated", "done", "error"}
FORBIDDEN_EVENTS = {"tool_call", "tool_result"}


def parse_sse_fixture(name: str) -> list[tuple[str, dict]]:
    raw = (FIXTURE_DIR / name).read_text(encoding="utf-8").strip()
    events = []
    for block in raw.split("\n\n"):
        lines = block.splitlines()
        event_line = next(line for line in lines if line.startswith("event: "))
        data_line = next(line for line in lines if line.startswith("data: "))
        events.append((event_line.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))))
    return events


def test_sse_recipe_update_fixture_matches_v1_contract():
    events = parse_sse_fixture("sse_recipe_update.txt")
    event_names = [name for name, _payload in events]

    assert event_names == ["token", "recipe_updated", "done"]
    assert set(event_names) <= ALLOWED_EVENTS
    assert not (set(event_names) & FORBIDDEN_EVENTS)
    assert events[0][1] == {"content": "已经调整为三人份，并减少了食用油用量。"}
    assert events[1][1] == {"recipe_id": 101, "version": 2}
    assert events[2][1] == {"message_id": 9001}


def test_v1_chat_api_skeleton_uses_recipe_session_contract():
    api_file = ROOT / "backend" / "app" / "api" / "chat.py"
    assert api_file.exists(), "V1 requires backend/app/api/chat.py."

    source = api_file.read_text(encoding="utf-8")
    assert 'prefix="/api/chat"' in source
    assert 'post("/sessions"' in source
    assert 'post("/sessions/{session_id}/messages"' in source
    assert "recipe_id" in source, "POST /api/chat/sessions request must accept recipe_id."
    assert "content" in source, "POST /api/chat/sessions/{session_id}/messages request must accept content."
    assert "recipe_updated" in source, "SSE stream must support recipe_updated."
    for event_name in FORBIDDEN_EVENTS:
        assert event_name not in source, f"V1 forbids SSE event {event_name}."
