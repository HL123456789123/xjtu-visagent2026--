import json
from pathlib import Path


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
