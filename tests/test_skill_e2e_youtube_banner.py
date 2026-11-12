"""#925 e2e: the `place_banner` page command really places the 2560×1440 banner on the canvas.

The real built app runs in headless Chromium against the real ComfyArt routes (the same harness
as test_e2e_skill_canvas_707 / _911). Nothing here calls a model: the banner files are PNGs drawn
in memory and labeled LOCAL FIXTURE, and compose_banner_text never touches WaveSpeed.

1. place_banner through the page command handler (window.__comfyartE2E.command -> HANDLERS,
   the same table the agent command bus dispatches to): exactly one new image node, its asset
   and the decoded file are 2560×1440, and it is the selected node.
2. The full server path: the real compose_banner_text tool reads a base already on the canvas
   (get_canvas in the page), writes the 2560×1440 final, and its place_banner call is executed
   by the same page. The final lands right of the base and is the only selected node.

dist/ must be a local build of this tree (`npx vite build`, not committed); a missing or stale
dist/ or a missing Chromium is a hard failure, never a skip.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from ComfyArt.api.mcp_tools import banner
from test_e2e_skill_canvas_707 import app_url, mock_ws  # noqa: F401 - same server + local mock WaveSpeed fixtures
from test_e2e_skill_sunburst_size_911 import _boot  # same page boot (UI language + e2e hook)

pw = pytest.importorskip("playwright.async_api")

ROOT = Path(__file__).resolve().parent.parent
W, H = 2560, 1440
GAP = 40  # src/jobs.ts GAP


@pytest.fixture(autouse=True, scope="module")
def built_dist():
    index = ROOT / "dist" / "index.html"
    if not index.is_file():
        pytest.fail("dist/index.html is missing: run `npx vite build` (local build, not committed) before this e2e")
    bundle = "".join(p.read_text(encoding="utf-8", errors="ignore") for p in (ROOT / "dist").rglob("*.js"))
    if "place_banner" not in bundle:
        pytest.fail("dist/ is stale (no 'place_banner'): run `npx vite build` (local, not committed) before this e2e")


@pytest.fixture(autouse=True)
def no_paid_keys(monkeypatch):
    for key in ("DEEPSEEK_API_KEY", "REPLICATE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def _png(w: int, h: int, rgb: tuple[int, int, int], label: str) -> bytes:
    img = Image.new("RGB", (w, h), rgb)
    ImageDraw.Draw(img).text((16, 16), f"LOCAL FIXTURE {label} {w}x{h}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _write(kind: str, subfolder: str, name: str, data: bytes) -> dict:
    import folder_paths
    path = folder_paths.STATE["base"] / kind / subfolder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"filename": name, "subfolder": subfolder, "type": kind}


async def _launch(p):
    try:
        return await p.chromium.launch()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"chromium not available, this e2e must not skip: {e}")


async def _clear(page):
    await page.evaluate("() => { const ed = window.__caEditor; ed.selectAll(); ed.deleteShapes(ed.getSelectedShapeIds()); ed.selectNone() }")


async def _command(page, action: str, args: dict) -> dict:
    return await page.evaluate("async ([a, args]) => window.__comfyartE2E.command(a, args)", [action, args])


async def _canvas(page) -> dict:
    """Every image node with its asset size and the decoded file's natural pixels, plus the selection."""
    return await page.evaluate(
        """async () => {
          const ed = window.__caEditor
          const images = []
          for (const s of ed.getCurrentPageShapes().filter((s) => s.type === 'image')) {
            const asset = ed.getAsset(s.props.assetId)
            const img = new Image()
            img.src = asset.props.src
            await img.decode()
            const b = ed.getShapePageBounds(s.id)
            images.push({ id: s.id, src: asset.props.src, asset: [asset.props.w, asset.props.h],
              natural: [img.naturalWidth, img.naturalHeight], node: [s.props.w, s.props.h],
              bounds: { x: b.x, y: b.y, w: b.w, h: b.h, maxX: b.maxX } })
          }
          return { images, selected: ed.getSelectedShapeIds() }
        }"""
    )


def _assert_banner(after: dict, before_ids: set[str], placed_id: str):
    new = [i for i in after["images"] if i["id"] not in before_ids]
    assert len(new) == 1, after
    node = new[0]
    assert node["id"] == placed_id, (node, placed_id)
    assert node["asset"] == [W, H], node
    assert node["natural"] == [W, H], node  # the actual file in the browser, not only metadata
    assert abs(node["node"][0] * H - node["node"][1] * W) < 1e-6, node  # node keeps 16:9, not cropped
    assert after["selected"] == [placed_id], after
    return node


@pytest.mark.parametrize("lang", ["zh", "en"])
async def test_skill_e2e_youtube_banner_place_banner_selects_2560x1440(app_url, mock_ws, lang):
    ref = _write("output", banner.SUBFOLDER, f"yt-banner-e2e-{lang}.png", _png(W, H, (47, 107, 255), f"banner {lang}"))
    ref["metadata"] = {"width": W, "height": H}
    async with pw.async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="zh-CN" if lang == "zh" else "en-US")
        await _boot(page, app_url, lang)
        await _clear(page)
        before = await _canvas(page)
        assert before["images"] == []
        out = await _command(page, banner.PLACE_ACTION, {"image": ref, "near": "", "name": "YouTube banner 2560×1440"})
        assert out["ok"] is True, out
        assert out["result"]["pixels"] == f"{W}x{H}", out
        after = await _canvas(page)
        node = _assert_banner(after, set(), out["result"]["id"])
        assert ref["filename"] in node["src"]
        assert node["node"] == [W / 2, H / 2], node  # no `near`: half size at the origin
        missing = await _command(page, banner.PLACE_ACTION, {"near": ""})
        assert missing["ok"] is False, missing  # no image ref: refused (errorText makes it user-facing), nothing placed
        assert len((await _canvas(page))["images"]) == 1
        await browser.close()


async def test_skill_e2e_youtube_banner_compose_places_final_next_to_base(app_url, mock_ws, monkeypatch):
    base_ref = _write("input", "", "yt-base-e2e.png", _png(2048, 1152, (250, 247, 240), "text-free base"))
    async with pw.async_playwright() as p:
        browser = await _launch(p)
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, locale="zh-CN")
        await _boot(page, app_url, "zh")
        await _clear(page)
        base_id = await page.evaluate(
            """(src) => {
              const ed = window.__caEditor
              const assetId = 'asset:yt-base-e2e'
              ed.createAssets([{ id: assetId, typeName: 'asset', type: 'image', meta: {},
                props: { name: 'base.png', src, w: 2048, h: 1152, mimeType: 'image/png', isAnimated: false } }])
              ed.createShape({ id: 'shape:ytbase', type: 'image', x: 0, y: 0, props: { assetId, w: 1024, h: 576 } })
              ed.selectNone()
              return 'shape:ytbase'
            }""",
            banner.view_url(base_ref),
        )
        before = await _canvas(page)
        calls = []

        async def to_page(action, args, project, timeout, chat=""):
            """The command bus hop: run the server's command in the real page handler."""
            calls.append(action)
            out = await _command(page, action, args)
            if not out["ok"]:
                raise RuntimeError(out["error"])
            return out["result"]

        monkeypatch.setattr(banner, "submit_command", to_page)
        res = await banner.compose_banner_text({
            "base": base_id, "skill": "youtube-channel-banner", "channel_name": "Loomi Studio",
            "tagline": "AI 绘画教程 · 创意工作流", "schedule": "每周二 / 周五更新", "brand_color": "#2F6BFF"})
        assert res["status"] == "done" and res["charged"] is False, res
        assert calls == ["get_canvas", banner.PLACE_ACTION]
        assert (res["width"], res["height"]) == (W, H)
        after = await _canvas(page)
        node = _assert_banner(after, {i["id"] for i in before["images"]}, res["id"])
        base = next(i for i in after["images"] if i["id"] == base_id)
        assert node["bounds"]["x"] == pytest.approx(base["bounds"]["maxX"] + GAP), (node, base)
        assert node["bounds"]["y"] == pytest.approx(base["bounds"]["y"])
        assert node["node"][0] == pytest.approx(base["bounds"]["w"])  # same width as the base it sits next to
        assert len(mock_ws["submits"]) == 0  # no model call on this path
        await browser.close()
