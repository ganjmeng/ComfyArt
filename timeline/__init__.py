import json
import os
from fractions import Fraction

import av
import numpy as np
from PIL import Image

import comfy.model_management
import comfy.utils
import folder_paths

from .audio import RATE, mix_audio
from .layers import Overlay, disk, paste

CLIPS = ("clip", "clip2", "clip3", "clip4", "clip5")
ENCODERS = {
    "mp4": ("h264", {"crf": "20", "preset": "medium"}, "aac"),
    "webm": ("libvpx-vp9", {"crf": "32", "b": "0", "deadline": "realtime", "cpu-used": "8", "row-mt": "1"}, "libopus"),
}
ROUNDING = 5e-4
ROOTS = (folder_paths.get_input_directory, folder_paths.get_output_directory, folder_paths.get_temp_directory)


def media_path(name: str) -> str:
    path = os.path.realpath(folder_paths.get_annotated_filepath(name))
    if not any(os.path.commonpath([path, os.path.realpath(root())]) == os.path.realpath(root()) for root in ROOTS):
        raise ValueError(f"{name} is outside the ComfyUI input, output and temp folders")
    if not os.path.isfile(path):
        raise FileNotFoundError(name)
    return path


class VisualClip:
    def __init__(self, spec: dict, width: int, height: int, path: str):
        self.kind = spec.get("type", "video")
        self.path = path
        self.start = float(spec["start"])
        self.duration = float(spec["duration"])
        self.end = self.start + self.duration
        self.offset = float(spec.get("offset", 0))
        self.speed = float(spec.get("speed", 1)) or 1.0
        self.track = int(spec.get("track", 0))
        self.fit = spec.get("fit", "contain")
        self.transition = spec.get("transition") or None
        self.transform = spec.get("transform")
        self.circle = spec.get("maskShape") == "circle"
        self.size = (width, height)
        self.container = None
        self.still = None
        self.current = None
        self.upcoming = None
        self.cache = (None, None)

    def source_time(self, t: float) -> float:
        return max(0.0, self.offset + (t - self.start) * self.speed)

    def _open(self):
        self.container = av.open(self.path)
        stream = self.container.streams.video[0]
        stream.thread_type = "AUTO"
        start = self.source_time(self.start - (self.transition or {}).get("duration", 0))
        self.container.seek(int(start / stream.time_base), stream=stream, backward=True)
        self.frames = self.container.decode(stream)
        self.current = next(self.frames, None)
        self.upcoming = next(self.frames, None)

    def place(self, rgb: np.ndarray):
        width, height = self.size
        h, w = rgb.shape[:2]
        scale = max(width / w, height / h) if self.fit == "cover" else min(width / w, height / h)
        sw, sh = max(1, round(w * scale)), max(1, round(h * scale))
        x, y = (width - sw) // 2, (height - sh) // 2
        if self.transform:
            s = float(self.transform[0][0])
            x, y = round(float(self.transform[0][2]) + x * s), round(float(self.transform[1][2]) + y * s)
            sw, sh = max(1, round(sw * s)), max(1, round(sh * s))
        img = np.asarray(Image.fromarray(rgb).resize((sw, sh), Image.BILINEAR))
        if not self.circle:
            return img, None, x, y
        d = min(sw, sh)
        ox, oy = (sw - d) // 2, (sh - d) // 2
        return img[oy:oy + d, ox:ox + d], disk(d), x + ox, y + oy

    def layer(self, t: float):
        if self.kind == "image":
            if self.still is None:
                self.still = self.place(np.asarray(Image.open(self.path).convert("RGB")))
            return self.still
        if self.container is None:
            self._open()
        target = self.source_time(t)
        while self.upcoming is not None and self.upcoming.time is not None and self.upcoming.time <= target:
            self.current, self.upcoming = self.upcoming, next(self.frames, None)
        if self.current is None:
            return None
        if self.cache[0] is not self.current:
            self.cache = (self.current, self.place(self.current.to_ndarray(format="rgb24")))
        return self.cache[1]

    def paint(self, below: np.ndarray, t: float) -> np.ndarray:
        layer = self.layer(t)
        return below if layer is None else paste(below, *layer)

    def close(self):
        if self.container is not None:
            self.container.close()
            self.container = None
            self.cache = (None, None)


def blend(kind: str, a: np.ndarray, b: np.ndarray, p: float) -> np.ndarray:
    h, w = a.shape[:2]
    if kind in ("black", "white"):
        tone = np.zeros_like(a) if kind == "black" else np.full_like(a, 255)
        src, k = (a, 1 - 2 * p) if p < 0.5 else (b, 2 * p - 1)
        return (src * k + tone * (1 - k)).astype(np.uint8)
    if kind in ("wipeleft", "wiperight", "wipeup", "wipedown"):
        out = a.copy()
        if kind == "wipeleft":
            out[:, : round(w * p)] = b[:, : round(w * p)]
        elif kind == "wiperight":
            out[:, w - round(w * p):] = b[:, w - round(w * p):]
        elif kind == "wipeup":
            out[h - round(h * p):] = b[h - round(h * p):]
        else:
            out[: round(h * p)] = b[: round(h * p)]
        return out
    if kind in ("slideleft", "slideright"):
        shift = round(w * p)
        out = np.empty_like(a)
        if kind == "slideleft":
            out[:, : w - shift], out[:, w - shift:] = a[:, shift:], b[:, : shift]
        else:
            out[:, shift:], out[:, :shift] = a[:, : w - shift], b[:, w - shift:]
        return out
    if kind == "zoom":
        scale = 1 + p * 0.5
        zw, zh = round(w / scale), round(h / scale)
        x, y = (w - zw) // 2, (h - zh) // 2
        zoomed = np.asarray(Image.fromarray(a[y:y + zh, x:x + zw]).resize((w, h), Image.BILINEAR))
        return (zoomed * (1 - p) + b * p).astype(np.uint8)
    return (a * (1 - p) + b * p).astype(np.uint8)


def compose(clips: list[VisualClip], t: float, width: int, height: int) -> np.ndarray:
    frame = np.zeros((height, width, 3), np.uint8)
    for track in sorted({c.track for c in clips}):
        lane = sorted((c for c in clips if c.track == track), key=lambda c: c.start)
        for i, clip in enumerate(lane):
            half = (clip.transition or {}).get("duration", 0) / 2
            prev = lane[i - 1] if i and abs(lane[i - 1].end - clip.start) < 1e-3 else None
            if prev is not None and half and clip.start - half <= t < clip.start + half:
                p = (t - (clip.start - half)) / (2 * half)
                frame = blend(clip.transition.get("type", "fade"), prev.paint(frame, t), clip.paint(frame, t), p)
                break
            if clip.start <= t < clip.end:
                nxt = lane[i + 1] if i + 1 < len(lane) else None
                nhalf = (nxt.transition or {}).get("duration", 0) / 2 if nxt is not None else 0
                if nhalf and abs(clip.end - nxt.start) < 1e-3 and t >= nxt.start - nhalf:
                    continue
                frame = clip.paint(frame, t)
                break
    return frame


def render(spec: dict, path: str, resolve=media_path):
    width, height = int(spec["width"]) // 2 * 2, int(spec["height"]) // 2 * 2
    fps = Fraction(str(spec.get("fps", 24))).limit_denominator(1001)
    clips = [VisualClip(c, width, height, resolve(c["src"])) for c in spec.get("video", [])]
    overlays = [Overlay(o, height, resolve(o["image"])) for o in spec.get("overlays", [])]
    total = float(spec.get("duration") or max([c.end for c in clips] + [o.end for o in overlays] + [0.0]))
    if total <= 0:
        raise ValueError("the timeline is empty")
    count = max(1, round(total * fps))
    sounds = [(c.path, s) for c, s in zip(clips, spec.get("video", [])) if c.kind == "video" and not s.get("muted")]
    audio = mix_audio(sounds + [(resolve(s["src"]), s) for s in spec.get("audio", [])], total)
    bar = comfy.utils.ProgressBar(count)
    codec, options, sound_codec = ENCODERS[spec.get("format", "mp4")]
    with av.open(path, "w") as out:
        video = out.add_stream(codec, rate=fps)
        video.width, video.height, video.pix_fmt = width, height, "yuv420p"
        video.options = options
        sound = out.add_stream(sound_codec, rate=RATE, layout="stereo") if audio is not None else None
        for i in range(count):
            comfy.model_management.throw_exception_if_processing_interrupted()
            t = float(i / fps) + ROUNDING
            frame = compose(clips, t, width, height)
            for o in overlays:
                if o.start <= t < o.end:
                    frame = o.apply(frame, t)
            for c in clips:
                if c.container is not None and t > c.end + 1:
                    c.close()
            out.mux(video.encode(av.VideoFrame.from_ndarray(frame, format="rgb24")))
            bar.update(1)
        out.mux(video.encode(None))
        if sound is not None:
            for start in range(0, audio.shape[1], 1024):
                chunk = av.AudioFrame.from_ndarray(np.ascontiguousarray(audio[:, start:start + 1024]), format="fltp", layout="stereo")
                chunk.sample_rate, chunk.pts = RATE, start
                out.mux(sound.encode(chunk))
            out.mux(sound.encode(None))
    for c in clips:
        c.close()


class Timeline:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"timeline": ("STRING", {"multiline": True}), "filename_prefix": ("STRING", {"default": "comfyart/edit"})},
            "optional": {key: ("VIDEO",) for key in CLIPS},
        }

    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = "render"
    CATEGORY = "ComfyArt"

    def render(self, timeline: str, filename_prefix: str, **clips):
        spec = json.loads(timeline)
        fmt = spec.get("format", "mp4")
        if fmt not in ENCODERS:
            raise ValueError(f"unsupported format {fmt!r}")
        folder, name, counter, subfolder, _ = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_output_directory())
        file = f"{name}_{counter:05}_.{fmt}"
        temps = {}
        if clips:
            os.makedirs(folder_paths.get_temp_directory(), exist_ok=True)
        try:
            for key, clip in clips.items():
                temps[f"@{key}"] = os.path.join(folder_paths.get_temp_directory(), f"{name}_{counter:05}_{key}.mp4")
                clip.save_to(temps[f"@{key}"])
            render(spec, os.path.join(folder, file), lambda src: temps.get(src) or media_path(src))
        finally:
            for temp in temps.values():
                os.remove(temp)
        return {"ui": {"images": [{"filename": file, "subfolder": subfolder, "type": "output"}], "animated": (True,)}}


NODE_CLASS_MAPPINGS = {"ComfyArtTimeline": Timeline}
NODE_DISPLAY_NAME_MAPPINGS = {"ComfyArtTimeline": "ComfyArt Timeline Render"}
