import json
from pathlib import Path

import pytest

from agent_retake.gather import gather

DEMO = Path(__file__).parent / "fixtures/claude/demo.jsonl"


def test_discovery_links_and_stability(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cwd = tmp_path / "orchard"
    cwd.mkdir()
    root = tmp_path / ".claude/projects/slug"
    root.mkdir(parents=True)
    src = root / "demo.jsonl"
    src.write_text(DEMO.read_text().replace("/synthetic/orchard", str(cwd)))
    first = gather([cwd, src])
    assert first == gather([src])
    msgs = first.sessions[0].messages
    assert [m.kind for m in msgs] == ["text", "call", "result", "text"]
    assert msgs[2].parent_id == msgs[1].id
    assert len(set(m.id for m in msgs)) == 4
    extra = tmp_path / "other.jsonl"
    extra.write_text(src.read_text().replace('"demo"', '"other"'))
    assert gather([src, extra]).sessions[0].messages == msgs


def test_live_tail_and_bad_interior(tmp_path):
    p = tmp_path / "demo.jsonl"
    p.write_text(DEMO.read_text() + '{"partial"')
    with pytest.warns(UserWarning, match="incomplete"):
        assert len(gather([p]).sessions[0].messages) == 4
    p.write_text(DEMO.read_text() + "private-value\n{}\n")
    with pytest.raises(ValueError, match="line 5") as err:
        gather([p])
    assert "private-value" not in str(err.value)


def test_identical_prompts_without_ids_remain_distinct(tmp_path):
    p = tmp_path / "demo.jsonl"
    row = json.loads(DEMO.read_text().splitlines()[0])
    del row["uuid"]
    p.write_text((json.dumps(row) + "\n") * 2)
    messages = gather([p]).sessions[0].messages
    assert len({m.id for m in messages}) == 2


def test_duplicate_native_record_is_not_a_duplicate_turn(tmp_path):
    p = tmp_path / "dup.jsonl"
    raw = DEMO.read_text()
    p.write_text(raw + raw.splitlines()[0] + "\n")
    assert len(gather([p]).sessions[0].messages) == 4


def test_invalid_session_time_does_not_echo_raw_data(tmp_path):
    p = tmp_path / "time.jsonl"
    p.write_text(DEMO.read_text().replace("2026-01-01T00:00:00Z","private-value"))
    with pytest.raises(ValueError) as err:
        gather([p])
    assert "private-value" not in str(err.value)
