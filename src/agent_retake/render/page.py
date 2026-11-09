from dataclasses import asdict
from importlib.resources import files
import json

from ..io import atomic
from ..scene import prepare_scene
from ..storyboard import Window, effective, load_board, load_config
from ..timing import compile_beat


def compile_board(path, beat_id=None):
    board = load_board(path)
    output, theme = effective(board, load_config(path))
    scene = prepare_scene(path, board=board, theme=theme)
    previous_end = None
    for b in scene.beats:
        if b.start is not None and b.end is not None:
            if previous_end is not None and b.start < previous_end:
                raise ValueError(f"beat {b.id}: overlap or beats out of timeline order")
            previous_end = b.end
    selected = []
    history = []
    for beat in scene.beats:
        if beat_id is None or beat.id == beat_id:
            selected.append((beat.id, compile_beat(beat, theme, history=history)))
        history.extend(beat.shots)
    if not selected:
        raise ValueError("no matching beats to render")
    return selected, output, scene.theme


def page_html(timeline, theme, *, window=None, controls=False):
    assets = files(__package__).joinpath("assets")
    data = json.dumps({"timeline": asdict(timeline), "theme": theme.model_dump(), "controls": controls,
                       "size": (window or Window()).model_dump()},
                      ensure_ascii=True).replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
    template = assets.joinpath("replay.html").read_text()
    return (template.replace("/* STYLES */", assets.joinpath("theme.css").read_text())
            .replace("/* CLOCK */", assets.joinpath("replay.js").read_text())
            .replace("/* DATA */", data))


def preview_html(path, beat_id):
    timelines, output, theme = compile_board(path, beat_id)
    ident, timeline = timelines[0]
    target = path.parent / output.dir / f"preview-{ident:02d}.html"
    atomic(target, page_html(timeline, theme, controls=True, window=output.window))
    return target
