from pathlib import Path
import subprocess


def test_private_artifacts_are_ignored():
    root = Path(__file__).resolve().parents[1]
    for name in ("data/raw.jsonl", "sessions.json", "summary.md", "storyboard.yaml", "clip.mov", "recording.wav"):
        assert subprocess.run(["git", "check-ignore", name], cwd=root).returncode == 0
