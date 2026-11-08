from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from agent_retake.cli import main
from agent_retake.storyboard import load_board, save_board
from test_gather import DEMO

ROOT = Path(__file__).resolve().parents[1]


def test_both_harnesses_discover_one_skill():
    canonical = ROOT / "skills/retake/SKILL.md"
    assert canonical.is_file()
    for root in [".claude", ".agents"]:
        assert (ROOT / root / "skills/retake/SKILL.md").samefile(canonical)
    assert (ROOT / "CLAUDE.md").read_text().strip() == "@AGENTS.md"


def test_installed_workflow_outside_checkout(tmp_path, monkeypatch):
    def cli(*args):
        return subprocess.run([str(Path(sys.executable).with_name("retake")), *map(str, args)],
                              cwd=tmp_path, capture_output=True, text=True)

    assert cli("gather", DEMO, "--out", tmp_path).returncode == 0
    board = tmp_path / "board.yaml"
    assert cli("storyboard", "init", "sessions.json", "--out", board).returncode == 0
    data = load_board(board)
    data.beats[0].cue = "invented orchard"
    data.beats[0].shots = data.beats[0].shots[:1]
    save_board(data, board)
    from agent_retake import align
    monkeypatch.setattr(align, "transcribe_words", lambda *a: ([align.Word("invented", 0, 1),
                                                               align.Word("orchard", 1, 2)], 4))
    assert main(["align", str(board), "--model-dir", "fixture", "--audio", "fixture.wav"]) == 0
    assert cli("scan", board).returncode == 0
    for command in [["render"], ["preview", "--beat", "1"], ["preview", "--html", "--beat", "1"]]:
        assert cli(*command, board).returncode != 0
    assert not (tmp_path / "footage").exists()
    assert cli("scan", board, "--review").returncode == 0
    assert cli("preview", board, "--beat", "1", "--html").returncode == 0
    data = load_board(board)
    from agent_retake.storyboard import Output, Window
    data.output = Output(fps=4, window=Window(width=320, height=240))
    save_board(data, board)
    assert cli("render", board).returncode == 0
    assert len(list((tmp_path / "footage").glob("*.mov"))) == 1
    with (tmp_path / "sessions.json").open("a") as stream:
        stream.write(" ")
    assert cli("render", board).returncode != 0
    assert cli("preview", board, "--beat", "1", "--html").returncode != 0
