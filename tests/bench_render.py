"""Run the reference workstation's 20-second benchmark through the installed CLI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from agent_retake.storyboard import Shot, load_board, save_board

FIXTURE = Path(__file__).parent / "fixtures/claude/demo.jsonl"


def run():
    with tempfile.TemporaryDirectory(prefix="retake-bench-") as tmp:
        directory = Path(tmp)
        board_path = directory / "storyboard.yaml"
        subprocess.run(["retake", "gather", str(FIXTURE), "--out", tmp], check=True)
        subprocess.run(["retake", "storyboard", "init", str(directory / "sessions.json"),
                        "--out", str(board_path)], check=True)
        board = load_board(board_path)
        beat = board.beats[0]
        beat.start, beat.end = 0.0, 20.0
        user, call, result, reply = beat.shots
        beat.shots = [user, Shot(message=call.message+".."+result.message, show="burst"), reply,
                      Shot(message=reply.message, show="condensed"), Shot(message=reply.message, show="still")]
        save_board(board, board_path)
        for args in (["scan", str(board_path)], ["scan", str(board_path), "--review"]):
            subprocess.run(["retake", *args], check=True)
        start = time.monotonic()
        subprocess.run(["retake", "render", str(board_path)], check=True)
        elapsed = time.monotonic()-start
        clip, = (directory / "footage").glob("*.mov")
        stream, = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(clip)]))["streams"]
        print(f"{stream['nb_frames']} frames, {stream['width']}×{stream['height']}, "
              f"{stream['profile']}, {elapsed:.2f} s, {clip.stat().st_size:,} bytes")
        if int(stream["nb_frames"]) != 600 or elapsed >= 120:
            raise SystemExit("reference render missed acceptance target")


if __name__ == "__main__":
    run()
