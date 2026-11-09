import json
import subprocess

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
    first = out / "01-retake-01.mov"
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


def pixels(path, fmt, capture_filter=None):
    args = ["ffmpeg", "-v", "error", "-i", str(path)]
    if capture_filter:
        args += ["-vf", capture_filter]
    return subprocess.check_output([*args, "-pix_fmt", fmt, "-frames:v", "1", "-f", "rawvideo", "-"])


def test_partial_edge_composites_against_light_and_dark(small):
    from agent_retake.render.encode import composite
    (small.parent / "retake.yaml").write_text('themes: {neutral: {background: "#c8c8c8"}}')
    scan_board(small)
    review_board(small)
    assert main(["render", str(small)]) == 0
    overlay, = (small.parent / "footage").glob("*.mov")
    alpha = pixels(overlay, "gray", "alphaextract")
    rgb = pixels(overlay, "rgb24")
    pos = next(i for i,v in enumerate(alpha) if i//320 > 220 and 75 < v < 180)
    # Opaque neighboring pixels give the terminal color, independent of RGB
    # stored at the partially transparent corner.
    color = rgb[(220*320+155)*3:(220*320+155)*3+3]
    for back in (0, 255):
        output = load_board(small).output
        output.background = "#000000" if not back else "#ffffff"
        full = small.parent / f"composite-{back}.mov"
        composite(overlay, full, output, 1, small.parent)
        # Crop the centered window from the actual opaque delivery codec.
        raw = pixels(full, "rgb24", "crop=320:240:1760:960")
        for channel, foreground in enumerate(color):
            expected = (foreground*alpha[pos] + back*(255-alpha[pos]))/255
            assert abs(raw[pos*3+channel] - expected) < 10


def test_project_selects_shot_label_without_pipeline_defaults():
    from agent_retake.render.capture import filename
    output = Output()
    assert output.shot == "retake"
    assert filename(output.name, 2, 3, False, "research") == "02-research-03.mov"


def test_second_beat_matches_rendering_it_on_its_own(small):
    board = load_board(small)
    second = board.beats[0].model_copy(deep=True)
    second.id = 2
    second.title = "The second exchange"
    second.start, second.end = 3.0, 6.0
    board.beats.append(second)
    save_board(board, small)
    scan_board(small)
    review_board(small)

    assert main(["render", str(small)]) == 0
    assert main(["render", str(small), "--beat", "2"]) == 0
    out = small.parent / "footage"
    def last_frame(name):
        return pixels(out / name, "rgba", "select=eq(n\\,11)")
    expected = last_frame("02-retake-02.mov")
    assert last_frame("01-retake-01.mov") != expected
    assert last_frame("02-retake-01.mov") == expected
