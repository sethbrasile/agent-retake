"""Check release archives and tracked paths before sharing."""
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def private_path(name):
    path = Path(name)
    if path.suffix == ".jsonl":
        return not name.startswith("tests/fixtures/")
    return (path.suffix.lower() in {".mov", ".mp4", ".wav", ".flac", ".mp3", ".m4a", ".bin"}
            or path.name in {"sessions.json", "summary.md", ".env"}
            or path.name.startswith("retake-redactions-")
            or (path.name.startswith("storyboard") and path.suffix in {".yaml", ".yml"})
            or "private" in path.parts)


def check():
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    if any(private_path(p) for p in tracked):
        raise ValueError("a tracked path may contain private episode data")
    wheel, = (ROOT / "dist").glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in names:
            if private_path(name) or not (name.startswith("agent_retake/") or ".dist-info/" in name):
                raise ValueError(f"unexpected wheel member: {name}")
        for asset in ("replay.html", "replay.js", "theme.css"):
            assert f"agent_retake/render/assets/{asset}" in names
    sdist, = (ROOT / "dist").glob("*.tar.gz")
    with tarfile.open(sdist) as archive:
        for item in archive.getmembers():
            name = item.name.partition("/")[2]
            if private_path(name):
                raise ValueError(f"unexpected source archive member: {name}")


if __name__ == "__main__":
    check()
