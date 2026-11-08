"""Match narration cues against a local model's word-level timestamps."""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .storyboard import load_board, save_board


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class Candidate:
    first: int
    stop: int
    score: float


def normalize(text):
    return " ".join(re.findall(r"\w+", text.casefold().replace("’", "").replace("'", "")))


def transcribe_words(audio: Path, model_dir: Path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ValueError("install the align extra: uv sync --extra align or pip install 'agent-retake[align]'") from None
    if not audio.is_file():
        raise ValueError("narration audio file is missing")
    if not all((model_dir / name).is_file() for name in ("config.json", "model.bin", "tokenizer.json")):
        raise ValueError("supply a complete local faster-whisper model directory, including tokenizer.json")
    model = WhisperModel(str(model_dir.resolve()), device="cpu", compute_type="int8",
                         cpu_threads=4, local_files_only=True)
    segments, info = model.transcribe(str(audio), word_timestamps=True)
    words = [Word(w.word, float(w.start), float(w.end)) for segment in segments for w in segment.words or []]
    return words, float(info.duration)


def candidates(tokens, cue, first):
    length = len(cue.split())
    hits = []
    best = 0
    for i in range(first, len(tokens)):
        for size in range(max(1, length-1), length+2):
            if i + size > len(tokens):
                continue
            window = " ".join(tokens[i:i+size])
            score = SequenceMatcher(None, cue, window, autojunk=False).ratio()
            best = max(best, score)
            if score >= 0.85:
                hits.append(Candidate(i, i+size, score))
    distinct = []
    for hit in sorted(hits, key=lambda h: (-h.score, h.first, h.stop)):
        if not any(hit.first < other.stop and hit.stop > other.first for other in distinct):
            distinct.append(hit)
    return distinct, best


def match_cues(beats, words, duration):
    words = [w for w in words if normalize(w.text)]
    tokens = [normalize(w.text) for w in words]
    cursor, starts, errors = 0, [], []
    for beat in beats:
        if beat.manual:
            if beat.start is None or beat.end is None or not 0 <= beat.start < beat.end <= duration:
                errors.append(f"beat {beat.id}: invalid manual interval")
                continue
            starts.append(beat.start)
            while cursor < len(words) and words[cursor].start < beat.end:
                cursor += 1
            continue
        cue = normalize(beat.cue)
        if not cue:
            errors.append(f"beat {beat.id}: supply a cue or set manual timing")
            continue
        hits, best = candidates(tokens, cue, cursor)
        if len(hits) != 1:
            positions = ", ".join(f"{words[h.first].start:.2f}s ({h.score:.2f})" for h in hits[:8])
            errors.append(f"beat {beat.id}: cue ambiguous at {positions}" if hits
                          else f"beat {beat.id}: cue not found (best score {best:.2f})")
            continue
        hit, = hits
        starts.append(words[hit.first].start)
        cursor = hit.stop
    if errors:
        raise ValueError("\n".join(errors))
    result = []
    for i, beat in enumerate(beats):
        following = starts[i+1] if i+1 < len(beats) else duration
        end = beat.end if beat.manual else following
        if not 0 <= starts[i] < end <= following <= duration:
            raise ValueError(f"beat {beat.id}: overlapping or invalid interval")
        result.append((starts[i], end))
    return result


def align_file(path, audio, model_dir):
    board = load_board(path)
    words, duration = transcribe_words(audio, model_dir)
    intervals = match_cues(board.beats, words, duration)
    for beat, (start, end) in zip(board.beats, intervals, strict=True):
        beat.start, beat.end = start, end
    save_board(board, path)
