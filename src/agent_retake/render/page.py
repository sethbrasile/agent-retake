from dataclasses import asdict
from importlib.resources import files
import json

from ..io import atomic
from ..scene import prepare_scene
from ..storyboard import effective, load_board, load_config
from ..timing import compile_beat


def compile_board(path, beat_id=None):
    board = load_board(path)
    scene = prepare_scene(path)
    output, theme = effective(board, load_config(path))
    selected = [(b.id, compile_beat(b, theme)) for b in scene.beats if beat_id is None or b.id == beat_id]
    if not selected:
        raise ValueError("no matching beats to render")
    return selected, output, theme


def page_html(timeline, theme, *, controls=False):
    assets = files(__package__).joinpath("assets")
    data = json.dumps({"timeline": asdict(timeline), "theme": theme.model_dump(), "controls": controls},
                      ensure_ascii=True).replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
    template = assets.joinpath("replay.html").read_text()
    return (template.replace("/* STYLES */", assets.joinpath("theme.css").read_text())
            .replace("/* CLOCK */", assets.joinpath("replay.js").read_text())
            .replace("/* DATA */", data))


def preview_html(path, beat_id):
    timelines, output, theme = compile_board(path, beat_id)
    ident, timeline = timelines[0]
    target = path.parent / output.dir / f"preview-{ident:02d}.html"
    atomic(target, page_html(timeline, theme, controls=True))
    return target
