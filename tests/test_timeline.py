from __future__ import annotations

import json

import av
import numpy as np
import pytest
from PIL import Image

from ComfyArt.timeline import Timeline, media_path
from ComfyArt.timeline.layers import STILL, motion


def make_clip(path, color, seconds=2.0, fps=24, tone=440.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as out:
        video = out.add_stream("h264", rate=fps)
        video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
        sound = out.add_stream("aac", rate=48000, layout="stereo")
        for i in range(int(seconds * fps)):
            out.mux(video.encode(av.VideoFrame.from_ndarray(np.full((48, 64, 3), color, np.uint8), format="rgb24")))
        out.mux(video.encode(None))
        t = np.arange(int(seconds * 48000)) / 48000
        wave = np.stack([np.sin(2 * np.pi * tone * t)] * 2).astype(np.float32) * 0.3
        for start in range(0, wave.shape[1], 1024):
            frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(wave[:, start:start + 1024]), format="fltp", layout="stereo")
            frame.sample_rate, frame.pts = 48000, start
            out.mux(sound.encode(frame))
        out.mux(sound.encode(None))


def frames_at(path, times):
    with av.open(str(path)) as c:
        frames = [(f.time, f.to_ndarray(format="rgb24")) for f in c.decode(video=0)]
    return [min(frames, key=lambda f: abs(f[0] - t))[1][24, 32] for t in times]


def test_renders_cuts_transition_overlay_and_audio(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "clips" / "red.mp4", (255, 0, 0))
    make_clip(fresh_user_dir / "output" / "clips" / "blue.mp4", (0, 0, 255), tone=660.0)
    overlay = np.zeros((48, 64, 4), np.uint8)
    overlay[:8, :, :] = (255, 255, 255, 255)
    (fresh_user_dir / "input").mkdir()
    Image.fromarray(overlay).save(fresh_user_dir / "input" / "sub.png")
    spec = {
        "width": 64, "height": 48, "fps": 24,
        "video": [
            {"src": "clips/red.mp4 [output]", "start": 0, "duration": 2, "offset": 0},
            {"src": "clips/blue.mp4 [output]", "start": 2, "duration": 2, "offset": 0, "transition": {"type": "fade", "duration": 1}},
        ],
        "overlays": [{"image": "sub.png", "start": 0, "duration": 1}],
        "audio": [{"src": "clips/red.mp4 [output]", "start": 1, "duration": 1, "speed": 1.5, "volume": 0.5}],
    }
    ui = Timeline().render(json.dumps(spec), "comfyart/edit")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["subfolder"] / ui["images"][0]["filename"]
    with av.open(str(out)) as c:
        assert c.streams.audio
        assert abs(float(c.duration / av.time_base) - 4) < 0.2
    red, mid, blue = frames_at(out, [0.5, 2.0, 3.5])
    assert red[0] > 200 and red[2] < 60
    assert 60 < mid[0] < 200 and 60 < mid[2] < 200
    assert blue[2] > 200 and blue[0] < 60
    with av.open(str(out)) as c:
        top = next(f for f in c.decode(video=0)).to_ndarray(format="rgb24")[2, 32]
    assert top.min() > 200


def test_speed_maps_source_time(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "a.mp4", (255, 0, 0), seconds=1)
    make_clip(fresh_user_dir / "output" / "b.mp4", (0, 255, 0), seconds=1)
    spec = {"width": 64, "height": 48, "fps": 24, "video": [
        {"src": "a.mp4 [output]", "start": 0, "duration": 0.5, "speed": 2},
        {"src": "b.mp4 [output]", "start": 0.5, "duration": 1, "muted": True},
    ]}
    ui = Timeline().render(json.dumps(spec), "edit")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    a, b = frames_at(out, [0.25, 1.0])
    assert a[0] > 200 and b[1] > 200


def test_cut_on_millisecond_rounded_start_holds_no_frame(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "a.mp4", (255, 0, 0), seconds=5.17)
    make_clip(fresh_user_dir / "output" / "b.mp4", (0, 0, 255), seconds=5.17)
    spec = {"width": 64, "height": 48, "fps": 30, "video": [
        {"src": "a.mp4 [output]", "start": 0, "duration": 5.167},
        {"src": "b.mp4 [output]", "start": 5.167, "duration": 5.167},
    ]}
    ui = Timeline().render(json.dumps(spec), "cut")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    with av.open(str(out)) as c:
        frames = [f.to_ndarray(format="rgb24")[24, 32] for f in c.decode(video=0)]
    assert frames[154][0] > 200 and frames[155][2] > 200


def test_video_audio_fades_around_transitions(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "a.mp4", (255, 0, 0), seconds=2)
    make_clip(fresh_user_dir / "output" / "b.mp4", (0, 0, 255), seconds=2)
    spec = {"width": 64, "height": 48, "fps": 24, "video": [
        {"src": "a.mp4 [output]", "start": 0, "duration": 2, "fadeOut": 0.5},
        {"src": "b.mp4 [output]", "start": 2, "duration": 2, "fadeIn": 0.5, "transition": {"type": "fade", "duration": 1}},
    ]}
    ui = Timeline().render(json.dumps(spec), "fades")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    with av.open(str(out)) as c:
        samples = np.concatenate([f.to_ndarray() for f in c.decode(audio=0)], axis=1)[0]
    level = lambda t: np.abs(samples[round(t * 48000):round((t + 0.05) * 48000)]).max()
    assert level(1.0) > 0.25
    assert level(1.95) < 0.05 and level(2.0) < 0.05
    assert 0.08 < level(1.7) < 0.22 and 0.08 < level(2.2) < 0.22
    assert level(3.0) > 0.25


def test_webm_export(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "a.mp4", (255, 0, 0), seconds=1)
    spec = {"width": 64, "height": 48, "fps": 24, "format": "webm", "video": [{"src": "a.mp4 [output]", "start": 0, "duration": 1}]}
    ui = Timeline().render(json.dumps(spec), "webm")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    assert out.suffix == ".webm"
    with av.open(str(out)) as c:
        assert c.streams.video[0].codec_context.name in ("vp9", "libvpx-vp9")
        assert c.streams.audio[0].codec_context.name in ("opus", "libopus")
        assert abs(float(c.duration / av.time_base) - 1) < 0.2
    (red,) = frames_at(out, [0.5])
    assert red[0] > 200 and red[2] < 60
    with pytest.raises(ValueError):
        Timeline().render(json.dumps({**spec, "format": "../x"}), "webm")


class FakeClip:
    def __init__(self, color=(0, 0, 255)):
        self.color = color

    def save_to(self, path):
        from pathlib import Path
        make_clip(Path(path), self.color, seconds=1, fps=24)


def test_splices_an_input_clip_by_time(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "src.mp4", (255, 0, 0), seconds=1, fps=30)
    spec = {"width": 64, "height": 48, "fps": 30, "video": [
        {"src": "src.mp4 [output]", "start": 0, "duration": 1},
        {"src": "@clip", "start": 1, "duration": 1 - 1 / 24, "offset": 1 / 24},
    ]}
    ui = Timeline().render(json.dumps(spec), "splice", clip=FakeClip())["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    with av.open(str(out)) as c:
        assert abs(float(c.duration / av.time_base) - (2 - 1 / 24)) < 0.1
    red, blue = frames_at(out, [0.5, 1.5])
    assert red[0] > 200 and blue[2] > 200
    assert not list((fresh_user_dir / "temp").glob("*_clip.mp4"))


def test_splices_several_input_clips(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "src.mp4", (255, 0, 0), seconds=1, fps=30)
    spec = {"width": 64, "height": 48, "fps": 30, "video": [
        {"src": "@clip", "start": 0, "duration": 1},
        {"src": "src.mp4 [output]", "start": 1, "duration": 1},
        {"src": "@clip2", "start": 2, "duration": 1},
    ]}
    ui = Timeline().render(json.dumps(spec), "splice2", clip=FakeClip(), clip2=FakeClip((0, 255, 0)))["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    blue, red, green = frames_at(out, [0.5, 1.5, 2.5])
    assert blue[2] > 200 and red[0] > 200 and green[1] > 200
    assert not list((fresh_user_dir / "temp").glob("*_clip*.mp4"))


def pixels(path, t, points):
    with av.open(str(path)) as c:
        frames = [(f.time, f.to_ndarray(format="rgb24")) for f in c.decode(video=0)]
    frame = min(frames, key=lambda f: abs(f[0] - t))[1]
    return [frame[y, x].astype(int) for x, y in points]


def test_transform_and_circle_mask_composite_over_lower_tracks(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "red.mp4", (255, 0, 0), seconds=1)
    make_clip(fresh_user_dir / "output" / "blue.mp4", (0, 0, 255), seconds=1)
    make_clip(fresh_user_dir / "output" / "green.mp4", (0, 255, 0), seconds=1)
    spec = {"width": 64, "height": 48, "fps": 24, "video": [
        {"src": "red.mp4 [output]", "start": 0, "duration": 1, "track": 0},
        {"src": "blue.mp4 [output]", "start": 0, "duration": 0.5, "track": 1, "transform": [[0.5, 0, 32], [0, 0.5, 0]], "muted": True},
        {"src": "green.mp4 [output]", "start": 0.5, "duration": 0.5, "track": 1, "maskShape": "circle", "muted": True},
    ]}
    ui = Timeline().render(json.dumps(spec), "pip")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    blue, red = pixels(out, 0.25, [(48, 12), (16, 36)])
    assert blue[2] > 200 and blue[0] < 60
    assert red[0] > 200 and red[2] < 60
    centre, corner, side = pixels(out, 0.75, [(32, 24), (3, 3), (60, 24)])
    assert centre[1] > 200 and centre[0] < 60
    assert corner[0] > 200 and corner[1] < 60
    assert side[0] > 200 and side[1] < 60


def test_untransformed_upper_track_still_covers_the_frame(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "red.mp4", (255, 0, 0), seconds=1)
    make_clip(fresh_user_dir / "output" / "blue.mp4", (0, 0, 255), seconds=1)
    spec = {"width": 64, "height": 48, "fps": 24, "video": [
        {"src": "red.mp4 [output]", "start": 0, "duration": 1, "track": 0},
        {"src": "blue.mp4 [output]", "start": 0, "duration": 1, "track": 1, "muted": True},
    ]}
    ui = Timeline().render(json.dumps(spec), "cover")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    for px in pixels(out, 0.5, [(1, 1), (32, 24), (62, 46)]):
        assert px[2] > 200 and px[0] < 60


def test_animated_text_overlay(fresh_user_dir):
    make_clip(fresh_user_dir / "output" / "black.mp4", (0, 0, 0), seconds=2)
    patch = np.zeros((16, 32, 4), np.uint8)
    patch[...] = (255, 255, 255, 255)
    (fresh_user_dir / "input").mkdir()
    Image.fromarray(patch).save(fresh_user_dir / "input" / "text.png")
    spec = {"width": 64, "height": 48, "fps": 24, "video": [{"src": "black.mp4 [output]", "start": 0, "duration": 2, "muted": True}], "overlays": [
        {"image": "text.png", "x": 16, "y": 16, "box": [16, 16, 32, 16], "start": 0, "duration": 2, "animation": {"type": "wipe-in", "duration": 1}},
        {"image": "text.png", "x": 16, "y": 0, "box": [16, 0, 32, 16], "start": 0, "duration": 2, "animation": {"type": "blur-in", "duration": 1}},
    ]}
    ui = Timeline().render(json.dumps(spec), "anim")["ui"]
    out = fresh_user_dir / "output" / ui["images"][0]["filename"]
    left, right, blurred = pixels(out, 0.5, [(20, 24), (44, 24), (32, 8)])
    assert left.min() > 200 and right.max() < 60
    assert 60 < blurred.mean() < 230
    left, right, sharp = pixels(out, 1.5, [(20, 24), (44, 24), (32, 8)])
    assert left.min() > 200 and right.min() > 200 and sharp.min() > 200


def test_text_motion_curves():
    assert motion("none", 0.5) == STILL
    start, mid, end = motion("fade", 0), motion("fade", 0.5), motion("fade", 1)
    assert start["opacity"] == pytest.approx(0, abs=1e-6) and 0.5 < mid["opacity"] < 1 and end == pytest.approx(STILL)
    assert motion("spring-up", 0)["dy"] == pytest.approx(28) and motion("spring-up", 1)["dy"] == pytest.approx(0, abs=1e-6)
    assert motion("pulse", 0.7)["scale"] == pytest.approx(1.06)
    assert motion("wave", 0.5)["dy"] == pytest.approx(-8)
    assert motion("blur-in", 0)["blur"] == pytest.approx(14) and motion("blur-in", 0)["scale"] == pytest.approx(1.06)


def test_rejects_paths_outside_comfy_folders(fresh_user_dir):
    with pytest.raises(ValueError):
        media_path("../../secret.mp4 [output]")
