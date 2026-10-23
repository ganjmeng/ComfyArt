"""#119: ComfyArt Timeline export (upstream ffmpeg node) at 24 fps with a music track, local files only (no paid calls)."""
from __future__ import annotations

import json
import wave

import av
import numpy as np

from ComfyArt.timeline import Timeline
from test_timeline import make_clip


def write_song(path, seconds=4.0, tone=330.0, rate=48000):
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(seconds * rate)) / rate
    pcm = (np.sin(2 * np.pi * tone * t) * 0.4 * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate)
        w.writeframes(pcm.tobytes())


def test_export_24fps_with_music_track(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "clips" / "a.mp4", (255, 0, 0))
    make_clip(fresh_user_dir / "output" / "clips" / "b.mp4", (0, 0, 255))
    write_song(fresh_user_dir / "output" / "audio" / "song.wav")
    # same shape as src/videoRender.ts: clips muted under a music track that starts 1 s into the song
    spec = {
        "width": 64, "height": 48, "fps": 24, "duration": 3, "format": "mp4",
        "video": [
            {"src": "clips/a.mp4 [output]", "start": 0, "duration": 1.5, "offset": 0, "muted": True},
            {"src": "clips/b.mp4 [output]", "start": 1.5, "duration": 1.5, "offset": 0, "muted": True},
        ],
        "audio": [{"src": "audio/song.wav [output]", "start": 0, "duration": 3, "offset": 1, "speed": 1, "volume": 1}],
        "overlays": [],
    }
    ui = Timeline().render(json.dumps(spec), "comfyart/edit")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["subfolder"] / ui["images"][0]["filename"]
    with av.open(str(out)) as c:
        v = c.streams.video[0]
        assert v.average_rate == 24
        assert c.streams.audio, "music track missing from export"
        assert abs(float(c.duration / av.time_base) - 3) < 0.2
        samples = np.concatenate([f.to_ndarray().reshape(-1) for f in c.decode(audio=0)])
    assert np.abs(samples).max() > 0.1  # the song is audible even though every clip is muted
