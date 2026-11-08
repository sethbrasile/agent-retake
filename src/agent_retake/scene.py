"""Only these reviewed, presentation-ready records may enter a replay page."""
from dataclasses import dataclass
import re

from .scan import load_inputs, validate
from .storyboard import Theme, effective, load_config, load_board, select


@dataclass(frozen=True)
class SafeShot:
    mode: str
    harness: str
    text: str
    highlights: list[str]


@dataclass(frozen=True)
class SafeBeat:
    id: int
    title: str
    start: float | None
    end: float | None
    shots: list[SafeShot]


@dataclass(frozen=True)
class SafeScene:
    beats: list[SafeBeat]
    theme: Theme


def condensed(text):
    blocks = []
    paragraph = []
    for raw in [*text.splitlines(), ""]:
        line = raw.strip()
        structural = re.match(r"^(?:#{1,6} |\*\*|[-*+] |\d+[.)] )", line)
        if not line or structural:
            if paragraph:
                blocks.append(" ".join(paragraph))
                paragraph.clear()
            if line:
                blocks.append(line)
        else:
            paragraph.append(line)
    return "\n".join(re.split(r"(?<=[.!?])\s+", block, maxsplit=1)[0] for block in blocks)


def prepare_scene(path, *, board=None, theme=None) -> SafeScene:
    board = board or load_board(path)
    if theme is None:
        _, theme = effective(board, load_config(path))
    conv, signature = load_inputs(board, path.parent)
    mapping, _ = validate(path, board, conv, signature, require_review=True, theme=theme)
    pattern = re.compile("|".join(map(re.escape, sorted(mapping, key=len, reverse=True)))) if mapping else None

    def clean(text):
        return pattern.sub(lambda m: mapping[m.group()], text) if pattern else text

    owners = {m.id: s for s in conv.sessions for m in s.messages}
    beats = []
    for beat in board.beats:
        shots = []
        for i, shot in enumerate(beat.shots, 1):
            try:
                msgs = select(conv, shot.message)
            except ValueError as err:
                raise ValueError(f"beat {beat.id} shot {i}: {err}") from None
            owner = owners[msgs[0].id]
            if shot.span and (len(msgs) != 1 or shot.show == "burst"):
                raise ValueError(f"beat {beat.id} shot {i}: a trim requires one text message")
            if shot.show == "burst":
                included = {m.id for m in msgs}
                # Recursively fold children only when their parent call is selected.
                pending = set(included)
                while pending:
                    added = {m.id for m in owner.messages if m.parent_id in pending} - included
                    included.update(added)
                    pending = added
                counts = {}
                for m in owner.messages:
                    if m.id in included and m.kind == "call":
                        name = clean(m.tool) or "tool"
                        counts[name] = counts.get(name, 0) + 1
                text = "\n".join(f"{name} × {n}" for name, n in counts.items()) or "Tool activity"
            else:
                text = "\n".join(clean(m.text) for m in msgs)
                if shot.span:
                    start, stop = shot.span
                    if not 0 <= start < stop <= len(text):
                        raise ValueError(f"beat {beat.id} shot {i}: trim outside reviewed text")
                    text = text[start:stop]
                if shot.show == "condensed":
                    text = condensed(text)
            shots.append(SafeShot(shot.show, owner.harness, text, [clean(v) for v in shot.highlight]))
        beats.append(SafeBeat(beat.id, clean(beat.title), beat.start, beat.end, shots))
    safe_theme = theme.model_copy(update={
        "font": clean(theme.font), "foreground": clean(theme.foreground), "background": clean(theme.background),
        "accents": {k: clean(v) for k, v in theme.accents.items()},
        "glyphs": {k: clean(v) for k, v in theme.glyphs.items()},
    })
    return SafeScene(beats, safe_theme)
