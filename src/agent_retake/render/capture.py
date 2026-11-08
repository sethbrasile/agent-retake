import fcntl
import os
import re
import string
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Error as BrowserError, sync_playwright

from .encode import check_clip, composite, encoder, frames
from .page import page_html


@contextmanager
def output_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another render is using this output directory") from None
        yield
    finally:
        os.close(fd)


def filename(pattern, beat, take, preview):
    for _, field, fmt, conv in string.Formatter().parse(pattern):
        if field is None:
            continue
        if (field not in {"beat", "shot", "take"} or conv or
                not re.fullmatch(r"(?:0?[1-9]\d?d)?", fmt) or field == "shot" and fmt):
            raise ValueError("unsupported output filename field or format")
    name = pattern.format(beat=beat, take=take, shot="agentreplay")
    if Path(name).name != name or not name.endswith(".mov") or name.startswith("."):
        raise ValueError("output name must be a MOV filename within the output directory")
    return name[:-4] + ("-preview.mov" if preview else ".mov")


def reserve(pattern, ident, directory, taken, preview, full):
    for take in range(1, 10000):
        name = filename(pattern, ident, take, preview)
        names = [name]
        if full:
            names.append(name[:-4] + "-4k.mov")
        if all(n not in taken and not (directory / n).exists() for n in names):
            taken.update(names)
            return names
        if "{take" not in pattern:
            break
    raise ValueError("output filename collision; use a template with {take}")


def record(page, timeline, theme, output, path, scale):
    page.set_content(page_html(timeline, theme))
    page.evaluate("document.fonts.ready")
    count = frames(timeline.duration, output.fps)
    with tempfile.TemporaryFile() as log, subprocess.Popen(
        encoder(path, output.fps), stdin=subprocess.PIPE, stderr=log
    ) as process:
        try:
            last_png = None
            end = timeline.shots[-1].end
            for i in range(count):
                t = i / output.fps
                if last_png is None:
                    page.evaluate("t => seek(t)", t)
                    png = page.screenshot(omit_background=True)
                    if t >= end:
                        last_png = png
                process.stdin.write(last_png or png)
            process.stdin.close()
            if process.wait():
                raise ValueError("FFmpeg failed to encode ProRes 4444")
        except BaseException:
            process.kill()
            process.wait()
            raise
    check_clip(path, width=round(output.window.width * scale), height=round(output.window.height * scale),
               fps=output.fps, count=count)


def export(board_path, compiled, *, preview=False):
    timelines, output, theme = compiled
    directory = board_path.parent / output.dir
    scale = 0.5 if preview else 1
    full = output.full_frame and not preview
    with output_lock(directory), tempfile.TemporaryDirectory(dir=directory) as tmp:
        stage = Path(tmp)
        used = set()
        jobs = [(ident, time, reserve(output.name, ident, directory, used, preview, full))
                for ident, time in timelines]
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport=output.window.model_dump(), device_scale_factor=scale,
                                        offline=True, service_workers="block")
                for _, time, names in jobs:
                    record(page, time, theme, output, stage / names[0], scale)
                    if full:
                        composite(stage / names[0], stage / names[1], output,
                                  frames(time.duration, output.fps), board_path.parent)
                browser.close()
        except BrowserError:
            raise ValueError("Chromium capture failed; check 'playwright install chromium' and process permissions") from None
        published = []
        report = []
        try:
            for ident, time, names in jobs:
                for name in names:
                    path = directory / name
                    os.link(stage / name, path)
                    published.append(path)
                    report.append(f"Beat {ident} ({time.duration:g} s)  {path}")
        except BaseException:
            for path in published:
                path.unlink(missing_ok=True)
            raise
    return report
