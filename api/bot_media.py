import base64
import io
import math
import warnings

import av
from PIL import Image, ImageDraw

from ._common import view_path

_ATTACH_MAX_PX = 1024
_ATTACH_JPEG_QUALITY = 85
# Planner copy only. EL long edge 1568; product floor is that this maximum stay ≥ 768.
# The stored upload and WaveSpeed refs are not passed through this.
PLANNER_LONG_EDGE = 1568
PLANNER_JPEG_QUALITY = 85
ATTACH_MAX_COUNT = 12
SHEET_FRAMES = 4
VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv")
MEDIA_ERRORS = (ValueError, OSError, av.FFmpegError)


def video_duration(container) -> float:
    stream = container.streams.video[0]
    if stream.duration and stream.time_base:
        return float(stream.duration * stream.time_base)
    return container.duration / av.time_base if container.duration else 0.0


def video_frames(path: str, count: int, start: float = 0.0, end: float | None = None) -> tuple[list[tuple[float, Image.Image]], float]:
    with av.open(path) as container:
        stream = container.streams.video[0]
        duration = video_duration(container)
        end = min(end if end is not None else duration, duration)
        start = max(0.0, min(start, end))
        times = [start + (end - start) * (i + 0.5) / count for i in range(count)]
        frames = []
        for at in times:
            container.seek(int(at / stream.time_base), stream=stream)
            for frame in container.decode(stream):
                if frame.time is None or frame.time >= at - 0.05:
                    frames.append((at, frame.to_image()))
                    break
    if not frames:
        raise ValueError("video has no frames")
    return frames, duration


def contact_sheet(frames: list[tuple[float, Image.Image]], size: int) -> Image.Image:
    cols = math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames) / cols)
    cell = size // cols
    w, h = frames[0][1].size
    ch = round(cell * h / w)
    sheet = Image.new("RGB", (cell * cols, ch * rows))
    draw = ImageDraw.Draw(sheet)
    for i, (at, im) in enumerate(frames):
        x, y = (i % cols) * cell, (i // cols) * ch
        sheet.paste(im.convert("RGB").resize((cell, ch)), (x, y))
        draw.rectangle((x, y, x + 52, y + 16), fill="black")
        draw.text((x + 4, y + 2), f"{at:.1f}s", fill="white")
    return sheet


class PlannerPixelOverflow(Exception):
    """The file's declared pixel count is above what the planner copy may decode."""


def planner_jpeg(data: bytes) -> dict:
    """Downscale a reference for the planning LLM. Does not touch the caller's bytes.

    Long edge is at most PLANNER_LONG_EDGE (1568). Smaller images are not enlarged.
    Re-encoded as JPEG so the sent pixels, not the file size, are what the vision
    guide's 1024-token-per-image cap applies to. A decompression-bomb header raises
    PlannerPixelOverflow instead of Pillow's error. Corrupt bytes still raise the
    decoder's own error for the caller to treat as unreadable.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                im = im.convert("RGB")
                im.thumbnail((PLANNER_LONG_EDGE, PLANNER_LONG_EDGE))
                width, height = im.size
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=PLANNER_JPEG_QUALITY)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PlannerPixelOverflow from None
    raw = buf.getvalue()
    return {"data": base64.b64encode(raw).decode("ascii"), "media_type": "image/jpeg",
            "width": width, "height": height, "jpeg_bytes": len(raw)}


def jpeg(im: Image.Image, max_px: int = _ATTACH_MAX_PX) -> dict:
    im = im.convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=_ATTACH_JPEG_QUALITY)
    return {"data": base64.b64encode(buf.getvalue()).decode("ascii"), "media_type": "image/jpeg"}


def render_attachment(url: str) -> dict:
    path = view_path(url)
    if path.lower().endswith(VIDEO_EXT):
        return jpeg(contact_sheet(video_frames(path, SHEET_FRAMES)[0], _ATTACH_MAX_PX))
    with Image.open(path) as im:
        return jpeg(im)
