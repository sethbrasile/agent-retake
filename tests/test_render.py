import json
import os
import subprocess
from pathlib import Path

import pytest

from agent_retake.cli import main
from agent_retake.scan import scan_board, review_board
from agent_retake.storyboard import load_board, save_board, Output, Window
from test_preview import timed
from test_scan import episode


@pytest.fixture
def small(timed):
    board = load_board(timed)
    board.output = Output(fps=4, window=Window(width=320, height=240))
    beat = board.beats[0]
    beat.shots = beat.shots[:1]
    beat.shots[0].show = "still"
    beat.end = 3.0
    save_board(board, timed)
    scan_board(timed)
    review_board(timed)
    return timed


def probe(path):
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams",
                                                "-of", "json", str(path)]))["streams"]


def test_video_alpha_and_takes(small):
    for _ in range(2):
        assert main(["render", str(small)]) == 0
    a, b = sorted((small.parent / "footage").glob("*.mov"))
    assert a != b
    stream, = probe(a)
    assert (stream["profile"], stream["codec_tag_string"]) == ("4444", "ap4h")
    assert (stream["width"], stream["height"], stream["nb_frames"]) == (320, 240, "12")
    assert stream["r_frame_rate"] == "4/1" and float(stream["duration"]) == 3
    mask = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(a), "-vf", "alphaextract,format=gray",
                                    "-frames:v", "1", "-f", "rawvideo", "-"])
    assert mask[0] == 0 and mask[120*320+160] == 255
    assert any(10 < v < 245 for v in mask)


def test_failure_keeps_previous_take(small, monkeypatch):
    from agent_retake.render import capture
    out = small.parent / "footage"
    out.mkdir()
    first = out / "01-agentreplay-01.mov"
    first.write_bytes(b"keep")
    monkeypatch.setattr(capture, "record", lambda *args: (_ for _ in ()).throw(ValueError("encoder failed")))
    assert main(["render", str(small)]) != 0
    assert list(out.iterdir()) == [first] and first.read_bytes() == b"keep"


def test_opaque_variant_and_preview(small):
    board = load_board(small)
    board.output.full_frame = True
    save_board(board, small)
    assert main(["render", str(small)]) == 0
    out = small.parent / "footage"
    stream, = probe(next(out.glob("*-4k.mov")))
    assert (stream["profile"], stream["width"], stream["height"]) == ("DNXHR HQ", 3840, 2160)
    assert main(["preview", str(small), "--beat", "1"]) == 0
    preview, = probe(next(out.glob("*preview*.mov")))
    assert preview["width"] == 160


def test_concurrent_output_refusal(tmp_path):
    from agent_retake.render.capture import output_lock
    with output_lock(tmp_path):
        with pytest.raises(ValueError, match="another render"):
            with output_lock(tmp_path):
                pass
