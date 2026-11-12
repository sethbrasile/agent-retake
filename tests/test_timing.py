import pytest
from agent_retake.scene import SafeBeat, SafeShot
from agent_retake.storyboard import Theme
from agent_retake.timing import compile_beat


@pytest.mark.parametrize(("mode", "text", "minimum"), [
    ("typed", "a" * 18, 1), ("burst", "Search × 2", 1.5), ("condensed", " ".join(["word"]*25), 6)])
def test_readable_minimum_and_tail(mode, text, minimum):
    shot = SafeShot(mode, "claude", text, [], "user" if mode == "typed" else "assistant")
    beat = SafeBeat(1, "Demo", 10, 12 + minimum, [shot])
    timeline = compile_beat(beat, Theme())
    assert timeline.shots[-1].end == pytest.approx(minimum)
    with pytest.raises(ValueError, match="beat 1.*overrun"):
        compile_beat(SafeBeat(1, "Demo", 10, 11 + minimum, [shot]), Theme())


def test_beat_hold_overrides_theme_tail():
    shot = SafeShot("full", "codex", "a" * 400, [], "assistant")
    timeline = compile_beat(SafeBeat(1, "Demo", 0, 20, [shot], hold=12), Theme(tail=2))
    assert timeline.shots[-1].end == pytest.approx(8)
    with pytest.raises(ValueError, match="beat 1.*overrun"):
        compile_beat(SafeBeat(1, "Demo", 0, 13, [shot], hold=12.9), Theme())


def test_storyboard_hold_is_validated():
    from agent_retake.storyboard import Beat
    with pytest.raises(ValueError):
        Beat(id=1, title="Demo", hold=-1, shots=[])
    assert Beat(id=1, title="Demo", hold=4.5, shots=[]).hold == 4.5
