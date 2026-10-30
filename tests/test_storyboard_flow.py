"""#168 (#33): storyboard full flow, generate -> on canvas, mocks only ($0, mocked WaveSpeed, no network).
The real page code (comfy.ts queuePrompt / cost confirm / waitForImages, wavespeed.ts wsBuilt, jobs.ts placeMedia) runs
in node against the real /comfyart/wavespeed routes; the clips are real tiny MP4s joined by the real ffmpeg step.
Checks the quoted price, the price in the confirm dialog and what is actually submitted all agree."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from ComfyArt.api import wavespeed
from conftest import node_ready
import test_wavespeed
from test_wavespeed import _meta, ws  # noqa: F401  (mocked WaveSpeed API)

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not node_ready() or not shutil.which("ffmpeg"), reason="needs node + npm install + ffmpeg")
T2V, I2V = "wavespeed-ai/minimax-h3/text-to-video", "bytedance/seedance-2.0/image-to-video"
SCENES = [{"prompt": "清晨的城市天际线，镜头缓慢推进", "duration": 5},
          {"prompt": "a cat jumps onto the window sill", "duration": 8},
          {"prompt": "close-up, the cat yawns", "duration": 4}]
INPUTS = {"feature": "text_to_video", "model": T2V, "prompt": "storyboard", "ratio": "16:9", "duration": 5,
          "resolution": "768p", "scenes": SCENES}
PRICE = {T2V: 0.05, I2V: 0.04}  # USD per second of clip, so every scene has its own price


def _clip(path: Path, color: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color={color}:s=96x54:d=0.5:r=10",
                    "-pix_fmt", "yuv420p", str(path)], check=True)


@pytest.fixture
async def clips(tmp_path):
    _clip(tmp_path / "red.mp4", "red")
    _clip(tmp_path / "blue.mp4", "blue")
    app = web.Application()
    async def serve(r):
        return web.FileResponse(tmp_path / r.match_info["name"])
    app.router.add_get("/clip/{name}", serve)
    server = TestServer(app)
    await server.start_server()
    yield {T2V: [str(server.make_url("/clip/red.mp4"))], I2V: [str(server.make_url("/clip/blue.mp4"))]}
    await server.close()


async def _page(base: str, env_extra: dict) -> dict:
    bundle = Path(os.environ.get("TMPDIR", "/tmp")) / f"sb168-{os.getpid()}.mjs"
    subprocess.run([str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/storyboard/rolldown.config.mjs"], cwd=ROOT,
                   check=True, capture_output=True, env={"PATH": os.environ["PATH"], "OUT": str(bundle)})
    proc = await asyncio.create_subprocess_exec("node", str(bundle), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                                                env={"PATH": os.environ["PATH"], "BASE": base, **env_extra})
    out, err = await asyncio.wait_for(proc.communicate(), 60)
    assert proc.returncode == 0, err.decode()
    return json.loads(out.decode().strip().splitlines()[-1])


async def test_storyboard_generate_to_canvas(ws, clips, bot_client, fresh_user_dir, monkeypatch):  # noqa: F811
    # the chain model (default image-to-video) in the mock catalog, with a duration field like the real one
    monkeypatch.setattr(test_wavespeed, "MODELS", test_wavespeed.MODELS + [_meta(I2V, {
        "prompt": {"type": "string"}, "image": {"type": "string"}, "duration": {"type": "integer", "enum": list(range(4, 16))},
        "resolution": {"type": "string", "enum": ["480p", "720p", "1080p"]}, "aspect_ratio": {"type": "string"}}, ("prompt", "image"))])
    ws["prices"].update({m: (lambda p: lambda inputs: round(p * int(inputs.get("duration") or 5), 4))(p) for m, p in PRICE.items()})
    ws["by_model"] = clips

    # 1. quote, as the generator card shows it before running
    est = await (await bot_client.post("/comfyart/wavespeed/estimate", json={"inputs": INPUTS})).json()
    expected = round(0.05 * 5 + 0.04 * 8 + 0.04 * 4, 4)  # first scene text-to-video, later scenes image-to-video
    assert est["price"] == pytest.approx(expected) and est["source"] == "quote" and est["confirm"] is True

    # 2-4. the real page code: run -> 409 cost confirm -> confirmed run -> poll history -> place on canvas
    page = await _page(str(bot_client.make_url("")).rstrip("/"), {"INPUTS": json.dumps(INPUTS), "W": "96", "H": "54"})
    runs = page["calls"]
    assert len(runs) == 2 and "confirmed" not in runs[0]["body"]["inputs"] and runs[1]["body"]["inputs"]["confirmed"] is True
    assert runs[0]["body"]["inputs"]["scenes"] == SCENES == runs[1]["body"]["inputs"]["scenes"]
    assert len(page["asked"]) == 1 and f" {-(-round(expected * 1_000_000) // 10_000)} 积分" in page["asked"][0]["desc"]  # dialog price == quote; #397 (PR #405) shows credits (uiCredits: ceil, 1 credit = $0.01)

    # what was submitted is exactly what was quoted: one task per scene, same models and durations
    submitted = [(m, p.get("duration")) for m, p in ws["submits"]]
    assert submitted == [(T2V, 5), (I2V, 8), (I2V, 4)]
    assert sum(PRICE[m] * d for m, d in submitted) == pytest.approx(est["price"])
    assert [p["prompt"] for _, p in ws["submits"]] == [s["prompt"] for s in SCENES]
    assert all(p.get("image") for _, p in ws["submits"][1:])  # chained from the previous clip's last frame

    # 5. on the canvas: one video asset + shape inside the frame, pointing at the joined storyboard MP4
    assert page["id"].startswith("ws:sb-") and len(page["refs"]) == 1
    ref = page["refs"][0]
    assert ref["filename"].endswith("_storyboard.mp4")
    [asset], [shape] = page["assets"], page["shapes"]
    assert asset["type"] == "video" and asset["props"]["mimeType"] == "video/mp4" and asset["props"]["isAnimated"] is True
    assert ref["filename"] in asset["props"]["src"] and asset["props"]["w"] == 96 and asset["props"]["h"] == 54
    assert shape["type"] == "video" and shape["parentId"] == "shape:frame1" and shape["props"]["assetId"] == asset["id"]
    assert shape["props"]["w"] == 480 and shape["props"]["h"] == pytest.approx(480 * 54 / 96)

    # the file the canvas shows is a real joined video: 3 clips of 5 frames, later clips drop their first frame
    import av
    with av.open(wavespeed._ref_path(ref)) as box:
        frames = list(box.decode(video=0))
    assert len(frames) == 5 + 4 + 4 and (frames[0].width, frames[0].height) == (96, 54)
