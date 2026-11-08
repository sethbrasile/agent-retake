import json
from pathlib import Path

import pytest
from agent_retake.gather import gather

FIX = Path(__file__).parent / "fixtures"


def test_codex_fallback_and_reverse_call_completion():
    msgs = gather([FIX / "codex/demo.jsonl"]).sessions[0].messages
    assert [m.text for m in msgs if m.kind == "text"] == ["Check the frost.", "A late frost.", "Try again."]
    parents = {m.call_id: m.id for m in msgs if m.kind == "call"}
    assert all(m.parent_id == parents[m.call_id] for m in msgs if m.kind == "result")


def test_pi_tree_and_cycle(tmp_path):
    p = FIX / "pi/demo.jsonl"
    msgs = gather([p]).sessions[0].messages
    assert [m.canonical for m in msgs] == [True, False, True]
    bad = tmp_path / "bad.jsonl"
    bad.write_text(p.read_text().replace('"parentId":"c"', '"parentId":"d"'))
    with pytest.raises(ValueError, match="cycle"):
        gather([bad])


def test_grok_group_and_updates_fallback(tmp_path):
    p = FIX / "grok"
    msgs = gather([p / "chat_history.jsonl", p / "updates.jsonl"]).sessions[0].messages
    assert [m.kind for m in msgs] == ["text", "text", "call", "result"]
    assert msgs[0].timestamp is None and msgs[-1].parent_id == msgs[-2].id
    for name in ["updates.jsonl", "summary.json"]:
        (tmp_path / name).write_bytes((p / name).read_bytes())
    updates = tmp_path / "updates.jsonl"
    updates.write_text(updates.read_text().replace('"2026-01-01T03:00:02Z"', "1767236402"))
    msgs = gather([tmp_path / "updates.jsonl"]).sessions[0].messages
    assert [m.text for m in msgs] == ["Cold weather."]


@pytest.mark.parametrize("family", ["pi", "codex", "claude"])
def test_malformed_payload_has_safe_error(tmp_path, family):
    src = FIX / family / "demo.jsonl"
    rows = src.read_text().splitlines()
    for bad in (None, [], 1, "invented-private-text"):
        row = json.loads(rows[1])
        row["payload" if family == "codex" else "message"] = bad
        p = tmp_path / "broken.jsonl"
        p.write_text(rows[0] + "\n" + json.dumps(row))
        try:
            gather([p])
        except ValueError as err:
            assert "invented-private-text" not in str(err)
