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
