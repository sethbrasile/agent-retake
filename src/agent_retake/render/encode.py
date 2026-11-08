import json
import math
import re
import subprocess
from fractions import Fraction


def frames(duration, fps):
    return max(1, math.floor(duration * fps + 0.5))


def encoder(path, fps):
    return ["ffmpeg", "-nostdin", "-v", "error", "-f", "image2pipe", "-framerate", str(fps),
            "-c:v", "png", "-i", "pipe:0", "-an", "-c:v", "prores_ks", "-threads", "8",
            "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-alpha_bits", "16", str(path)]


def check_clip(path, *, width, height, fps, count, full_frame=False):
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
                          capture_output=True)
    if proc.returncode:
        raise ValueError("ffprobe could not read the rendered clip")
    streams = json.loads(proc.stdout)["streams"]
    if len(streams) != 1:
        raise ValueError("expected one silent video stream")
    stream = streams[0]
    valid = (stream["width"] == width and stream["height"] == height and
             int(stream.get("nb_frames", 0)) == count and
             Fraction(stream["r_frame_rate"]) == fps)
    if full_frame:
        valid &= stream.get("profile") == "DNXHR HQ" and stream.get("pix_fmt") == "yuv422p"
    else:
        valid &= stream.get("codec_tag_string") == "ap4h" and stream.get("pix_fmt", "").startswith("yuva444")
    if not valid:
        raise ValueError("rendered clip failed codec, geometry, frame count or fps checks")


def composite(window, target, output, count, directory):
    fps = output.fps
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", output.background):
        bg = ["-f", "lavfi", "-i", f"color=c=0x{output.background[1:]}:s=3840x2160:r={fps}"]
    else:
        image = directory / output.background
        if not image.is_file() or image.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise ValueError("background must be a hex color or a local PNG, JPEG or WebP image")
        bg = ["-loop", "1", "-framerate", str(fps), "-i", str(image)]
    graph = ("[0:v]scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160[bg];"
             "[bg][1:v]overlay=(W-w)/2:(H-h)/2:alpha=straight:format=auto")
    proc = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *bg, "-i", str(window),
                           "-filter_complex_threads", "4", "-filter_complex", graph, "-frames:v", str(count),
                           "-an", "-c:v", "dnxhd", "-profile:v", "dnxhr_hq", "-pix_fmt", "yuv422p",
                           "-threads", "4", str(target)], capture_output=True)
    if proc.returncode:
        raise ValueError("FFmpeg could not composite the 4K background")
    check_clip(target, width=3840, height=2160, fps=fps, count=count, full_frame=True)
