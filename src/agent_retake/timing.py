from dataclasses import dataclass, field

from .scene import SafeBeat, SafeShot
from .storyboard import Theme


@dataclass(frozen=True)
class TimedShot:
    shot: SafeShot
    start: float
    end: float


@dataclass(frozen=True)
class Timeline:
    title: str
    duration: float
    shots: list[TimedShot]
    history: list[SafeShot] = field(default_factory=list)


def minimum(shot, theme):
    if shot.mode == "typed":
        return max(0.1, len(shot.text) / theme.typed_cps)
    if shot.mode == "burst":
        return theme.burst_seconds
    if shot.mode == "condensed":
        return max(0.1, len(shot.text.split()) * 60 / theme.condensed_wpm)
    if shot.mode == "full":
        return max(0.25, min(2, len(shot.text) / 100))
    return 0.25


def compile_beat(beat: SafeBeat, theme: Theme, *, history=()) -> Timeline:
    if beat.start is None or beat.end is None or beat.end <= beat.start:
        raise ValueError(f"beat {beat.id}: set start and end to a positive interval")
    if not beat.shots:
        raise ValueError(f"beat {beat.id}: add at least one shot")
    duration = beat.end - beat.start
    active = duration - theme.tail
    lengths = [minimum(s, theme) for s in beat.shots]
    required = sum(lengths)
    if required > active + 1e-8:
        raise ValueError(f"beat {beat.id}: overrun {required-active:.2f}s; trim or split the shots")
    shots = []
    cursor = 0.0
    for shot, length in zip(beat.shots, lengths, strict=True):
        end = cursor + length * active / required
        shots.append(TimedShot(shot, cursor, end))
        cursor = end
    return Timeline(beat.title, duration, shots, list(history))
