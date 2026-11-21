import base64
import io
import math
import threading
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
# Declared pixels above this are refused before decode. Pillow's global
# MAX_IMAGE_PIXELS is not changed outside the locked planner call.
PLANNER_MAX_PIXELS = 250_000_000
_planner_pixels_lock = threading.Lock()
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


class ImageUnreadable(Exception):
    """The chat attachment is not a local image file, or its pixels do not decode."""


def _encode_planner(im: Image.Image) -> dict:
    frame = im.convert("RGB")
    frame.thumbnail((PLANNER_LONG_EDGE, PLANNER_LONG_EDGE))
    width, height = frame.size
    buf = io.BytesIO()
    frame.save(buf, "JPEG", quality=PLANNER_JPEG_QUALITY)
    raw = buf.getvalue()
    return {"data": base64.b64encode(raw).decode("ascii"), "media_type": "image/jpeg",
            "width": width, "height": height, "jpeg_bytes": len(raw)}


def planner_jpeg(data: bytes) -> dict:
    """Downscale a reference for the planning LLM. Does not touch the caller's bytes.

    Every format may be up to PLANNER_MAX_PIXELS (250MP). A larger declared size,
    a Pillow bomb error past that cap, or a decode MemoryError raises
    PlannerPixelOverflow. JPEG is drafted down before load. Other formats are
    reduced before the 1568px thumbnail. Smaller images are not enlarged. The
    result is JPEG quality 85 so the vision guide's 1024-token cap applies to
    the sent pixels. Corrupt bytes still raise the decoder's own error.
    Image.MAX_IMAGE_PIXELS is restored before this function returns.
    """
    with _planner_pixels_lock:
        previous = Image.MAX_IMAGE_PIXELS
        try:
            # Own cap, only for this call. Pillow errors above twice this value;
            # we refuse anything above the cap from the header before that.
            Image.MAX_IMAGE_PIXELS = PLANNER_MAX_PIXELS
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as im:
                    width, height = im.size
                    if width < 1 or height < 1 or width * height > PLANNER_MAX_PIXELS:
                        raise PlannerPixelOverflow
                    if (im.format or "").upper() == "JPEG":
                        long_edge = max(width, height)
                        if long_edge > PLANNER_LONG_EDGE:
                            scale = PLANNER_LONG_EDGE / long_edge
                            im.draft("RGB", (max(1, round(width * scale)), max(1, round(height * scale))))
                        im.load()
                        return _encode_planner(im)
                    im.load()
                    long_edge = max(im.size)
                    if long_edge > PLANNER_LONG_EDGE * 2:
                        factor = max(2, long_edge // (PLANNER_LONG_EDGE * 2))
                        reduced = im.reduce(factor)
                    else:
                        reduced = im
                    return _encode_planner(reduced)
        except Image.DecompressionBombError:
            raise PlannerPixelOverflow from None
        except MemoryError:
            raise PlannerPixelOverflow from None
        finally:
            Image.MAX_IMAGE_PIXELS = previous


def jpeg(im: Image.Image, max_px: int = _ATTACH_MAX_PX) -> dict:
    im = im.convert("RGB")
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=_ATTACH_JPEG_QUALITY)
    return {"data": base64.b64encode(buf.getvalue()).decode("ascii"), "media_type": "image/jpeg"}


def render_attachment(url: str) -> dict:
    """Chat-send thumbnail. Uses the planner decode lock, not a bare Image.open.

    JPEG is drafted down before load. Other formats decode, then thumbnail.
    Declared size above 250MP, a decompression bomb, or MemoryError raises
    PlannerPixelOverflow. A remote URL or bytes that do not decode raise
    ImageUnreadable. Image.MAX_IMAGE_PIXELS is restored before return.
    """
    try:
        path = view_path(url)
    except ValueError as exc:
        # A remote or non-file URL cannot be decoded. A missing local file
        # stays the caller's existing not-found error.
        if str(exc).startswith("not a ComfyUI file URL"):
            raise ImageUnreadable(str(exc)) from exc
        raise
    if path.lower().endswith(VIDEO_EXT):
        return jpeg(contact_sheet(video_frames(path, SHEET_FRAMES)[0], _ATTACH_MAX_PX))
    with open(path, "rb") as handle:
        data = handle.read()
    try:
        planned = planner_jpeg(data)
    except (OSError, SyntaxError, ValueError) as exc:
        raise ImageUnreadable(str(exc)) from exc
    return {"data": planned["data"], "media_type": planned["media_type"]}
