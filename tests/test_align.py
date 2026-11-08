import pytest
from agent_retake.align import Word, match_cues
from agent_retake.storyboard import Beat
from test_scan import episode


def beat(ident, cue, **kwargs):
    return Beat(id=ident, title="test", cue=cue, shots=[], **kwargs)


def words(*parts):
    return [Word(text, float(i), i + 0.75) for i, text in enumerate(parts)]


def test_timed_words_and_manual_intervals():
    beats = [beat(1, "Late Frost!"), beat(2, "", start=3.0, end=4.0, manual=True),
             beat(3, "start over")]
    result = match_cues(beats, words("Well", "late", "frost", "today", "start", "over"), 7)
    assert result == [(1, 3), (3, 4), (4, 7)]


@pytest.mark.parametrize("cue", ["start", "weather"])
def test_ambiguous_or_missing(cue):
    with pytest.raises(ValueError, match="beat 1"):
        match_cues([beat(1, cue)], words("start", "again", "start"), 3)


def test_failed_align_preserves_board(episode, monkeypatch):
    from agent_retake import align
    original = episode.read_bytes()
    monkeypatch.setattr(align, "transcribe_words", lambda *a: (words("unrelated"), 1))
    with pytest.raises(ValueError):
        align.align_file(episode, None, None)
    assert episode.read_bytes() == original
