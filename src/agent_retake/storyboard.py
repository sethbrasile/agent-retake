import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, PositiveInt, ValidationError

from .io import atomic, read_yaml
from .model import Conversation, Record


class Window(Record):
    width: int = Field(default=1920, ge=160, le=7680)
    height: int = Field(default=1200, ge=120, le=4320)


class Output(Record):
    dir: str = "footage"
    name: str = "{beat:02d}-{shot}-{take:02d}.mov"
    fps: int = Field(default=30, ge=1, le=120)
    window: Window = Field(default_factory=Window)
    full_frame: bool = False
    background: str = "#20222b"


class Theme(Record):
    font: str = "monospace"
    size: int = Field(default=28, ge=8, le=120)
    padding: int = Field(default=32, ge=4, le=120)
    foreground: str = "#e4e7ed"
    background: str = "#181b22"
    typed_cps: float = Field(default=18, gt=0, allow_inf_nan=False)
    condensed_wpm: float = Field(default=250, gt=0, allow_inf_nan=False)
    burst_seconds: float = Field(default=1.5, gt=0, allow_inf_nan=False)
    tail: float = Field(default=2, ge=0, allow_inf_nan=False)
    accents: dict[str, str] = Field(default_factory=dict)
    glyphs: dict[str, str] = Field(default_factory=dict)


class Shot(Record):
    message: str
    show: Literal["typed", "burst", "full", "condensed", "still"]
    span: list[int] | None = Field(default=None, min_length=2, max_length=2)
    highlight: list[str] = Field(default_factory=list)


class Beat(Record):
    id: PositiveInt
    title: str
    why: str = ""
    cue: str = ""
    start: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    manual: bool = False
    shots: list[Shot]


class Rule(Record):
    id: str = ""
    match: str | None = None
    replace: str | None = None
    keep: bool = False
    reason: str = ""


class Review(Record):
    reviewed: bool = False
    sessions_sha256: str = ""
    scan_version: int = 0
    rules: list[Rule] = Field(default_factory=list)
    review_sha256: str = ""
    sidecar: str = ""


class Storyboard(Record):
    version: Literal[1] = 1
    title: str = "Untitled"
    sessions: list[str] = Field(min_length=1)
    theme: str = "neutral"
    output: Output = Field(default_factory=Output)
    redactions: Review = Field(default_factory=Review)
    beats: list[Beat]


class Config(Record):
    theme: str = "neutral"
    themes: dict[str, Theme] = Field(default_factory=dict)
    output: Output = Field(default_factory=Output)


def load_config(board_path):
    path = board_path.parent / "retake.yaml"
    return Config.model_validate(read_yaml(path) or {}) if path.exists() else Config()


def effective(board, config):
    output = config.output.model_dump()
    for key, val in board.output.model_dump(exclude_unset=True).items():
        if key == "window":
            output[key].update(val)
        else:
            output[key] = val
    name = board.theme if "theme" in board.model_fields_set else config.theme
    themes = {"neutral": Theme(), **config.themes}
    if name not in themes:
        raise ValueError("unknown theme in storyboard or retake.yaml")
    return Output.model_validate(output), themes[name]


def select(conversation, selector):
    start, sep, end = selector.partition("..")
    for s in conversation.sessions:
        ids = [m.id for m in s.messages]
        if start in ids:
            a = ids.index(start)
            if not sep:
                return [s.messages[a]]
            if end in ids[a:]:
                return s.messages[a:ids.index(end) + 1]
    raise ValueError("unknown message or invalid same-session range")


def init_storyboard(conversation: Conversation) -> Storyboard:
    beats = []
    for s in conversation.sessions:
        beat = None
        for m in s.messages:
            if not m.canonical:
                continue
            if m.role == "user" and m.kind == "text":
                n = len(beats) + 1
                beat = Beat(id=n, title=f"Beat {n}", shots=[])
                beats.append(beat)
            if beat:
                mode = "typed" if m.role == "user" else "full" if m.kind == "text" else "burst"
                beat.shots.append(Shot(message=m.id, show=mode))
    return Storyboard(sessions=["sessions.json"], beats=beats)


def load_board(path: Path) -> Storyboard:
    try:
        board = Storyboard.model_validate(read_yaml(path))
    except ValidationError as err:
        locations = ["/".join(map(str, issue["loc"])) for issue in err.errors()]
        raise ValueError("invalid storyboard field(s): " + ", ".join(locations)) from None
    ids = [b.id for b in board.beats]
    if len(ids) != len(set(ids)):
        raise ValueError("beat IDs must be unique")
    return board


def save_board(board, path):
    obj = board.model_dump(exclude_unset=True, exclude_none=True)
    atomic(path, yaml.safe_dump(obj, sort_keys=False, allow_unicode=True))


def initialize(bundle, out):
    board = init_storyboard(Conversation.model_validate_json(bundle.read_bytes()))
    board.sessions = [os.path.relpath(bundle.resolve(), out.parent.resolve())]
    if out.exists():
        raise ValueError("storyboard already exists; choose a new output path")
    save_board(board, out)
