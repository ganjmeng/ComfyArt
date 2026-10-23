from fractions import Fraction

import av
import numpy as np

RATE = 48000


def _decode(path: str, offset: float, length: float) -> np.ndarray | None:
    with av.open(path) as container:
        if not container.streams.audio:
            return None
        stream = container.streams.audio[0]
        container.seek(int(offset / stream.time_base), stream=stream, backward=True)
        resampler = av.AudioResampler(format="fltp", layout="stereo", rate=RATE)
        parts, first = [], None
        for frame in container.decode(stream):
            if first is None:
                first = frame.time or 0.0
            parts += [f.to_ndarray() for f in resampler.resample(frame)]
            if frame.time is not None and frame.time > offset + length + 1:
                break
        parts += [f.to_ndarray() for f in resampler.resample(None)]
    if not parts:
        return None
    samples = np.concatenate(parts, axis=1)
    skip = max(0, round((offset - (first or 0.0)) * RATE))
    return samples[:, skip:skip + round(length * RATE)]


def _tempo(samples: np.ndarray, speed: float) -> np.ndarray:
    graph = av.filter.Graph()
    node = graph.add_abuffer(format="fltp", sample_rate=RATE, layout="stereo", time_base=Fraction(1, RATE))
    source = node
    rest = speed
    while rest > 2.0 or rest < 0.5:
        step = 2.0 if rest > 2.0 else 0.5
        stage = graph.add("atempo", str(step))
        node.link_to(stage)
        node, rest = stage, rest / step
    stage = graph.add("atempo", f"{rest:.6f}")
    node.link_to(stage)
    sink = graph.add("abuffersink")
    stage.link_to(sink)
    graph.configure()
    frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(samples, dtype=np.float32), format="fltp", layout="stereo")
    frame.sample_rate, frame.pts, frame.time_base = RATE, 0, Fraction(1, RATE)
    source.push(frame)
    source.push(None)
    parts = []
    while True:
        try:
            parts.append(sink.pull().to_ndarray())
        except (av.error.BlockingIOError, av.error.EOFError):
            break
    return np.concatenate(parts, axis=1) if parts else samples[:, :0]


def _place(mix: np.ndarray, samples: np.ndarray, start: float, volume: float, fade_in: float, fade_out: float):
    n = samples.shape[1]
    if not n:
        return
    gain = np.full(n, volume, np.float32)
    if fade_in > 0:
        k = min(n, round(fade_in * RATE))
        gain[:k] *= np.linspace(0, 1, k, dtype=np.float32)
    if fade_out > 0:
        k = min(n, round(fade_out * RATE))
        gain[n - k:] *= np.linspace(1, 0, k, dtype=np.float32)
    at = round(start * RATE)
    end = min(mix.shape[1], at + n)
    if end > at:
        mix[:, at:end] += samples[:, : end - at] * gain[: end - at]


def mix_audio(sources: list[tuple[str, dict]], total: float) -> np.ndarray | None:
    mix = np.zeros((2, round(total * RATE)), np.float32)
    placed = False
    for path, clip in sources:
        speed = float(clip.get("speed", 1)) or 1.0
        duration = float(clip["duration"])
        samples = _decode(path, float(clip.get("offset", 0)), duration * speed)
        if samples is None:
            continue
        if abs(speed - 1) > 1e-3:
            samples = _tempo(samples, speed)
        _place(mix, samples[:, : round(duration * RATE)], float(clip["start"]), float(clip.get("volume", 1)), float(clip.get("fadeIn", 0)), float(clip.get("fadeOut", 0)))
        placed = True
    return np.clip(mix, -1, 1) if placed else None
