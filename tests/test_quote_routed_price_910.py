"""#910: the quote card names and prices the model the call is routed to, and a GPT Image 2.6 edit is priced
with its input images.

Data point (studio-model, main a64a8e0c, 2026-11-12 02:57 Asia/Shanghai): routed openai/gpt-image-2.6-flare/edit
with one reference, quoted list $0.05 / discounted $0.045, charged $0.0585 (= $0.065 list x 90%). The edit was
priced without its `images`. WaveSpeed's free price API (tests/fixtures/wavespeed_price_2_6_910.json, every
quality x resolution cell x 0/1/2 images) prices a 2.6 edit as its text-to-image cell + $0.015 per input image.

Mocks only: no key, no network, $0.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import aiohttp
import pytest

from ComfyArt.api import gif_image, wavespeed
from ComfyArt.api.auto_models import skill_pin
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.bot.plan_quote import build_quote

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
LIVE = json.loads((FIX / "wavespeed_price_2_6_910.json").read_text())["rows"]
CATALOG = json.loads((FIX / "wavespeed_catalog_subset.json").read_text())

FLARE_T2I = "openai/gpt-image-2.6-flare/text-to-image"
FLARE_EDIT = "openai/gpt-image-2.6-flare/edit"
SUNBURST_T2I = "openai/gpt-image-2.6-sunburst/text-to-image"
SUNBURST_EDIT = "openai/gpt-image-2.6-sunburst/edit"
FOUR = (FLARE_T2I, FLARE_EDIT, SUNBURST_T2I, SUNBURST_EDIT)


def _live(model, quality="medium", resolution="1k", images=0, **extra):
    for r in LIVE:
        if (r["model_id"], r["quality"], r["resolution"], r["images"]) == (model, quality, resolution, images) \
                and all(r.get(k) == v for k, v in extra.items()) and (extra or not (r.get("mask_image") or r.get("markup_image"))):
            return r
    raise KeyError((model, quality, resolution, images, extra))


def _mock_price(inputs: dict, model: str) -> float:
    """The live price API shape: cell + $0.015 per input image (images + mask_image), as recorded."""
    if model not in FOUR:
        return 0.04  # another routed model (e.g. the multi-reference row): not part of #910's four
    n = len(inputs.get("images") or []) + (1 if inputs.get("mask_image") else 0)
    if model.endswith("/text-to-image"):
        n = 0
    return _live(model, str(inputs.get("quality") or "medium"), str(inputs.get("resolution") or "1k"), min(n, 2))["price"]


def _mock_charged(inputs: dict, model: str) -> float:
    """What the account is charged (discounted_price). wavespeed.quote returns this for the card."""
    row = _live(model, str(inputs.get("quality") or "medium"), str(inputs.get("resolution") or "1k"),
                min(len(inputs.get("images") or []), 2) if not str(model).endswith("/text-to-image") else 0)
    return row["discounted_price"]


async def _no_models(feature):
    return []


@pytest.fixture
def cat(monkeypatch):
    async def catalog():
        return {m: CATALOG[m] for m in FOUR}
    monkeypatch.setattr(wavespeed, "catalog", catalog)
    wavespeed._quotes.clear()
    yield
    wavespeed._quotes.clear()


# ---- the four prices against the WaveSpeed catalog and the live price API ----

@pytest.mark.parametrize("model,list_usd", [(FLARE_T2I, 0.05), (SUNBURST_T2I, 0.05), (FLARE_EDIT, 0.065), (SUNBURST_EDIT, 0.065)])
def test_catalog_base_price_of_the_four_models(model, list_usd):
    # WaveSpeed catalog base_price: text-to-image medium 1k, edit medium 1k with one input image
    assert CATALOG[model]["base_price"] == list_usd
    assert wavespeed.base_price_of(model, CATALOG[model]) == list_usd
    assert gif_image.documented_usd(model, "medium", "1k", 0 if model.endswith("text-to-image") else 1) == list_usd


@pytest.mark.parametrize("row", LIVE, ids=lambda r: f"{r['model_id']}:{r['quality']}:{r['resolution']}:{r['images']}"
                         + (":mask" if r.get("mask_image") else "") + (":markup" if r.get("markup_image") else ""))
def test_price_table_matches_every_recorded_price_api_cell(row):
    n = row["images"] + (1 if row.get("mask_image") or row.get("markup_image") else 0)
    if row["model_id"].endswith("/text-to-image"):
        assert gif_image.TABLE_26[(row["quality"], row["resolution"])] == row["price"]
    assert gif_image.documented_usd(row["model_id"], row["quality"], row["resolution"], n) == row["price"]
    assert round(row["price"] * 0.9, 6) == row["discounted_price"]


def test_edit_input_surcharge_is_the_recorded_step():
    assert gif_image.EDIT_INPUT_USD == 0.015
    for m in (FLARE_EDIT, SUNBURST_EDIT):
        assert _live(m, images=0)["price"] == 0.05      # what the #910 quote priced (no images sent)
        assert _live(m, images=1)["price"] == 0.065     # what the run was charged at (list)
        assert _live(m, images=1)["discounted_price"] == 0.0585  # the balance delta of pred 0cea96f7
        assert _live(m, images=2)["price"] == 0.08
        assert _live(m, images=1, mask_image=True)["price"] == 0.08


# ---- the quote carries what is submitted ----

async def test_priced_inputs_count_the_mask_as_an_input(cat):
    priced = await wavespeed.priced_inputs(FLARE_EDIT, {"feature": "image_edit", "prompt": "p", "image": "a.png", "mask": "m.png"})
    assert priced["images"] == ["ref-1"] and priced["mask_image"]
    assert _mock_price(priced, FLARE_EDIT) == 0.08
    plain = await wavespeed.priced_inputs(FLARE_EDIT, {"feature": "image_edit", "prompt": "p", "image": "a.png"})
    assert "mask_image" not in plain and _mock_price(plain, FLARE_EDIT) == 0.065


@pytest.mark.parametrize("model", [FLARE_EDIT, SUNBURST_EDIT])
async def test_price_api_down_estimate_counts_input_images(cat, monkeypatch, model):
    class Down:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            raise aiohttp.ClientError("down")

        async def __aexit__(self, *a):
            return False
    monkeypatch.setattr(wavespeed.aiohttp, "ClientSession", Down)
    monkeypatch.setattr(wavespeed, "_headers", lambda: {})
    for n, usd in ((1, 0.065), (2, 0.08), (3, 0.095)):
        price, source = await wavespeed.quote(model, {"feature": "image_edit", "prompt": "p", "images": [f"r{i}.png" for i in range(n)]})
        assert (price, source) == (usd, "estimate")
    price, _ = await wavespeed.quote(model, {"feature": "image_edit", "prompt": "p", "images": ["r.png"], "quality": "high", "resolution": "2k"})
    assert price == _live(model, "high", "2k", 1)["price"] == 0.135


# ---- the quote card: routed model + its references ----

def test_quote_route_counts_refs_and_base_like_the_page():
    _m, both = canvas.quote_route("generate_image", {"prompt": "p", "refs": ["shape:a"], "base": "shape:b"})
    assert both["images"] == ["ref-1", "ref-2"]
    t2i, plain = canvas.quote_route("generate_image", {"prompt": "a cat"})
    assert t2i and "images" not in plain


async def test_studio_model_skill_quotes_the_pinned_edit_model_price():
    """#920 pin (main 88cbd358): studio-model with a reference is quoted as its skills pin, not the
    image_edit feature default. The expected model is read from api/auto_models.json (not hardcoded)."""
    pinned = skill_pin("studio-model")["edit_model"]
    args = {"prompt": "p", "refs": ["shape:a"], "ratio": "3:4", "skill": "studio-model"}
    model, inputs = canvas.quote_route("generate_image", args)
    assert model == pinned
    assert inputs["images"] == ["ref-1"] and inputs["ratio"] == "3:4"
    assert "refs" not in inputs
    expected = _mock_price(inputs, pinned)

    async def pricer(m, inp):
        return _mock_price(inp, m)

    quote = await build_quote(
        [{"text": "棚拍", "tool": "generate_image", "model": "", "arguments": args}],
        "zh", threshold=0.0, pricer=pricer, models_for=_no_models, router=canvas.quote_route)
    assert quote is not None and not quote.lines[0].approx
    assert quote.lines[0].amount == expected
    if pinned in (FLARE_EDIT, SUNBURST_EDIT):
        assert expected == 0.065


async def test_no_skill_quotes_the_feature_default_flare_edit_price():
    """With no skill, one reference routes to the image_edit feature default
    (openai/gpt-image-2.6-flare/edit) and is priced as that model."""
    default = wavespeed.load_config()["features"]["image_edit"]["default"]
    assert default == FLARE_EDIT
    args = {"prompt": "p", "refs": ["shape:a"]}
    model, inputs = canvas.quote_route("generate_image", args)
    assert model == default
    assert inputs["images"] == ["ref-1"]
    expected = _mock_price(inputs, default)
    assert expected == 0.065

    async def pricer(m, inp):
        return _mock_price(inp, m)

    quote = await build_quote(
        [{"text": "修图", "tool": "generate_image", "model": "", "arguments": args}],
        "zh", threshold=0.0, pricer=pricer, models_for=_no_models, router=canvas.quote_route)
    assert quote is not None and not quote.lines[0].approx
    assert quote.lines[0].amount == expected


async def test_auto_card_names_and_prices_the_routed_edit_model_not_the_dearest():
    """#910 body: the card said Nano Banana Pro (dearest image_edit model) while the call ran on 2.6 flare edit."""
    seen = []

    async def pricer(model, inputs):
        seen.append((model, dict(inputs)))
        return _mock_price(inputs, model)

    async def models_for(feature):
        return [("google/nano-banana-pro/edit", 0.14), (FLARE_EDIT, 0.065)]

    steps = [{"text": "棚拍", "tool": "generate_image", "model": "",
              "arguments": {"prompt": "studio", "refs": ["shape:garment"], "ratio": "3:4", "skill": "studio-model"}},
             {"text": "再来一张", "tool": "generate_image", "model": "",
              "arguments": {"prompt": "studio", "refs": ["shape:garment", "shape:pose"], "ratio": "3:4"}}]
    quote = await build_quote(steps, "zh", threshold=0.0, pricer=pricer, models_for=models_for, router=canvas.quote_route)
    assert quote is not None
    routed = [canvas.quote_route(s["tool"], s["arguments"])[0] for s in steps]
    assert [m for m, _ in seen] == routed
    assert seen[0][1]["images"] == ["ref-1"] and seen[1][1]["images"] == ["ref-1", "ref-2"]
    assert "Nano Banana Pro" not in quote.lines[0].text and "nano-banana-pro" not in quote.lines[0].text
    assert not quote.lines[0].approx and quote.lines[0].amount == _mock_price({"images": ["ref-1"]}, routed[0])
    if routed[0] in (FLARE_EDIT, SUNBURST_EDIT):
        assert quote.lines[0].amount == 0.065


async def test_without_router_the_old_behaviour_is_unchanged():
    async def pricer(model, inputs):
        return None

    async def models_for(feature):
        return [("acme/dear", 0.3)]
    q = await build_quote([{"text": "a", "tool": "generate_image", "model": "", "arguments": {"prompt": "p"}}],
                          "zh", threshold=0.0, pricer=pricer, models_for=models_for)
    assert q is not None and q.lines[0].approx and "dear" in q.lines[0].text


async def test_budget_price_of_a_named_call_with_refs_counts_its_references(monkeypatch):
    from ComfyArt.bot.local_llm import LocalLlmProvider
    seen = []

    async def price_one(self, model, inputs):
        seen.append((model, dict(inputs)))
        return _mock_price(inputs, model)
    monkeypatch.setattr(LocalLlmProvider, "_price_one", price_one)
    provider = LocalLlmProvider.__new__(LocalLlmProvider)
    p = await provider._price_call("generate_image", {"prompt": "p", "model": FLARE_EDIT, "refs": ["shape:a"]})
    assert seen and seen[-1][1]["images"] == ["ref-1"]
    assert p == _mock_price({"images": ["ref-1"]}, seen[-1][0])


async def test_clothing_swap_quote_uses_resolution_tier_and_two_images():
    """Real paid clothing-swap request: openai/gpt-image-2.6-sunburst/edit, aspect_ratio 3:4,
    medium quality, 2 input images (person + garment).

    resolution 2k → list $0.13, charged $0.117 = 0.9 x (tier base + $0.015 x images).
    resolution 1k → list $0.08, charged $0.072 (locks both tier and image count).
    size '1536*2048' alone (no width/height/resolution) is not used to infer a
    tier — same as build_payload on main — so the quote is the WaveSpeed default
    1k, charged $0.072.
    """
    pinned = skill_pin("clothing-swap")["model"]
    cell = lambda res: gif_image.TABLE_26[("medium", res)]
    step = gif_image.EDIT_INPUT_USD

    def args_of(*, resolution=None, size=None, width=None, height=None):
        out = {"prompt": "换装", "skill": "clothing-swap", "refs": ["shape:person", "shape:garment"],
               "ratio": "3:4", "quality": "medium"}
        if resolution is not None:
            out["resolution"] = resolution
        if size is not None:
            out["size"] = size
        if width is not None:
            out["width"] = width
        if height is not None:
            out["height"] = height
        return out

    async def quoted(args):
        seen = []

        async def pricer(model, inputs):
            seen.append((model, dict(inputs)))
            return _mock_charged(inputs, model)

        quote = await build_quote(
            [{"text": "换装", "tool": "generate_image", "model": "", "arguments": args}],
            "zh", threshold=0.0, pricer=pricer, models_for=_no_models, router=canvas.quote_route)
        return quote, seen

    # --- 2k, 2 images: the real paid body ---
    model, inputs = canvas.quote_route("generate_image", args_of(resolution="2k"))
    assert model == pinned == SUNBURST_EDIT
    assert inputs["resolution"] == "2k" and inputs["images"] == ["ref-1", "ref-2"]
    list_2k, charged_2k = _live(pinned, "medium", "2k", 2)["price"], _live(pinned, "medium", "2k", 2)["discounted_price"]
    assert list_2k == gif_image.documented_usd(pinned, "medium", "2k", 2) == round(cell("2k") + step * 2, 4) == 0.13
    assert charged_2k == round(0.9 * (cell("2k") + step * 2), 6) == 0.117
    quote, seen = await quoted(args_of(resolution="2k"))
    assert quote is not None and not quote.lines[0].approx
    assert seen[0][0] == pinned and seen[0][1]["resolution"] == "2k" and seen[0][1]["images"] == ["ref-1", "ref-2"]
    assert quote.lines[0].amount == 0.117

    # Product path: apply_generate keeps 1536x2048 and has no resolution key; quote must still
    # use the submitted 2k tier (long side 2048), not default 1k ($0.045 / $0.072).
    product = args_of(width=1536, height=2048)
    assert "resolution" not in product and "size" not in product
    model, inputs = canvas.quote_route("generate_image", product)
    assert model == pinned and inputs["resolution"] == "2k" and inputs["images"] == ["ref-1", "ref-2"]
    quote, seen = await quoted(product)
    assert seen[0][1]["resolution"] == "2k" and quote.lines[0].amount == 0.117

    # --- 1k, 2 images: locks both tier and image count ---
    model, inputs = canvas.quote_route("generate_image", args_of(resolution="1k"))
    assert model == pinned and inputs["resolution"] == "1k" and inputs["images"] == ["ref-1", "ref-2"]
    list_1k, charged_1k = _live(pinned, "medium", "1k", 2)["price"], _live(pinned, "medium", "1k", 2)["discounted_price"]
    assert list_1k == gif_image.documented_usd(pinned, "medium", "1k", 2) == round(cell("1k") + step * 2, 4) == 0.08
    assert charged_1k == round(0.9 * (cell("1k") + step * 2), 6) == 0.072
    quote, seen = await quoted(args_of(resolution="1k"))
    assert seen[0][1]["resolution"] == "1k" and seen[0][1]["images"] == ["ref-1", "ref-2"]
    assert quote.lines[0].amount == 0.072

    # --- size 1536*2048 alone must not infer 2k (matches main submit: no resolution, default 1k) ---
    size_only = args_of(size="1536*2048")
    assert "resolution" not in size_only and "width" not in size_only and "height" not in size_only
    model, inputs = canvas.quote_route("generate_image", size_only)
    assert model == pinned and inputs.get("resolution") != "2k" and inputs.get("size") == "1536*2048"
    assert inputs["images"] == ["ref-1", "ref-2"]
    assert wavespeed.resolution_from_inputs(size_only, ["1k", "2k", "4k"]) is None
    quote, seen = await quoted(size_only)
    assert seen[0][1].get("resolution") != "2k"
    assert quote.lines[0].amount == 0.072  # 1k default + 2 images, not the 2k $0.117
    assert gif_image.documented_usd(pinned, "medium", str(inputs.get("resolution") or "1k"), 2) == 0.08


async def test_clothing_swap_size_only_build_payload_omits_resolution():
    """Real build_payload (network stubbed: https images are passed through, no upload, $0)
    for a clothing-swap call with only size=1536*2048 submits no resolution (main behavior:
    WaveSpeed default 1k), matching the quote of $0.072.
    """
    pinned = skill_pin("clothing-swap")["model"]
    assert pinned == SUNBURST_EDIT
    schema = wavespeed._schema(CATALOG[pinned])
    enum = ((schema.get("properties") or {}).get("resolution") or {}).get("enum")
    default = ((schema.get("properties") or {}).get("resolution") or {}).get("default")
    assert enum == ["1k", "2k", "4k"] and default == "1k"
    inputs = {
        "prompt": "换装",
        "size": "1536*2048",
        "images": ["https://example.invalid/person.png", "https://example.invalid/garment.png"],
        "quality": "medium",
        "ratio": "3:4",
    }
    assert "width" not in inputs and "height" not in inputs and "resolution" not in inputs
    payload = await wavespeed.build_payload(None, schema, inputs, pinned)
    assert "resolution" not in payload  # WaveSpeed default 1k; no auto-upgrade from the size string
    assert payload.get("aspect_ratio") == "3:4"
    assert len(payload.get("images") or []) == 2
    assert wavespeed.resolution_from_inputs(inputs, enum) is None
    routed_model, routed = canvas.quote_route(
        "generate_image",
        {"prompt": "换装", "skill": "clothing-swap", "refs": ["shape:person", "shape:garment"],
         "ratio": "3:4", "quality": "medium", "size": "1536*2048"})
    assert routed_model == pinned and routed.get("resolution") != "2k"
    assert (payload.get("resolution") or default) == (wavespeed.resolution_from_inputs(inputs, enum) or default) == "1k"


def test_price_endpoint_ignores_size_string_endpoint_behavior_only():
    """WaveSpeed POST /api/v3/model/price with size=1536*2048 and no resolution
    (recorded 2026-11-12 08:52:39-08:52:41 Asia/Shanghai, balance 29.731866
    unchanged, /workspace/910-capture/price-probe-clothing-swap-2k.json) returns
    the default 1k cell: 2 images list $0.08 / charged $0.072; no images $0.05 /
    $0.045. The product quote/submit path matches that 1k default (size is not
    used to infer 2k).
    """
    assert _live(SUNBURST_EDIT, "medium", "1k", 2)["price"] == 0.08
    assert _live(SUNBURST_EDIT, "medium", "1k", 2)["discounted_price"] == 0.072
    assert _live(SUNBURST_EDIT, "medium", "1k", 0)["price"] == 0.05
    assert _live(SUNBURST_EDIT, "medium", "1k", 0)["discounted_price"] == 0.045
    assert wavespeed.resolution_from_inputs({"size": "1536*2048"}, ["1k", "2k", "4k"]) is None
    assert gif_image.documented_usd(SUNBURST_EDIT, "medium", "1k", 2) == 0.08


MAIN_SUBMIT_SHA = "88cbd35874028f0c9f30a33c7f8dbd7fcc91ca3f"

# clothing-swap generate_image shapes used by the parity and main-byte-identical tests
_PAYLOAD_BASE = {
    "prompt": "换装",
    "images": ["https://example.invalid/person.png", "https://example.invalid/garment.png"],
    "quality": "medium",
    "ratio": "3:4",
}
_PAYLOAD_SHAPES = {
    "size-only": {"size": "1536*2048"},
    "width-height": {"width": 1536, "height": 2048},
    "explicit-2k": {"resolution": "2k"},
    "explicit-1k": {"resolution": "1k"},
    "none": {},
    "explicit-2k-with-size": {"resolution": "2k", "size": "1536*2048"},
    "explicit-1k-with-wh": {"resolution": "1k", "width": 1536, "height": 2048},
}


def _schema_tier(schema):
    res = (schema.get("properties") or {}).get("resolution") or {}
    return res.get("enum") or [], res.get("default")


def _effective_tier(payload_or_inputs, schema, *, from_payload=False):
    enum, default = _schema_tier(schema)
    if from_payload:
        return payload_or_inputs.get("resolution") or default
    return wavespeed.resolution_from_inputs(payload_or_inputs, enum, default) or default


def _main_wavespeed():
    """Load api/wavespeed.py as of main 88cbd358, as a sibling of the current api package.

    JSON catalogs are the current tree's files (symlinked next to the temp module) so
    model_defaults match; the comparison is the submit logic, not catalog drift.
    """
    name = "ComfyArt.api._wavespeed_main_88cbd358"
    if name in sys.modules and hasattr(sys.modules[name], "build_payload"):
        return sys.modules[name]
    src = subprocess.check_output(["git", "show", f"{MAIN_SUBMIT_SHA}:api/wavespeed.py"], cwd=ROOT)
    tmp = Path(tempfile.mkdtemp(prefix="ws-main-88cbd358-"))
    path = tmp / "wavespeed.py"
    path.write_bytes(src)
    api = ROOT / "api"
    for fn in ("curated_models.json", "wavespeed_models.json", "model_display.json"):
        (tmp / fn).symlink_to(api / fn)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("shape_name", list(_PAYLOAD_SHAPES))
async def test_quote_tier_matches_build_payload_resolution(shape_name):
    """Submitted resolution (or schema default when omitted) equals the tier the quote uses."""
    pinned = skill_pin("clothing-swap")["model"]
    assert pinned == SUNBURST_EDIT
    schema = wavespeed._schema(CATALOG[pinned])
    enum, default = _schema_tier(schema)
    shape = _PAYLOAD_SHAPES[shape_name]
    inputs = {**_PAYLOAD_BASE, **shape}
    payload = await wavespeed.build_payload(None, schema, inputs, pinned)
    submitted = _effective_tier(payload, schema, from_payload=True)
    quote_tier = _effective_tier(inputs, schema)
    assert submitted == quote_tier
    assert quote_tier == (wavespeed.resolution_from_inputs(inputs, enum, default) or default)

    route_args = {"prompt": "换装", "skill": "clothing-swap",
                  "refs": ["shape:person", "shape:garment"],
                  "quality": "medium", "ratio": "3:4", **shape}
    routed_model, routed = canvas.quote_route("generate_image", route_args)
    assert routed_model == pinned
    routed_tier = routed.get("resolution") or default
    assert routed_tier == submitted

    seen = []

    async def pricer(model, price_inputs):
        seen.append((model, dict(price_inputs)))
        return _mock_charged(price_inputs, model)

    quote = await build_quote(
        [{"text": "换装", "tool": "generate_image", "model": "", "arguments": route_args}],
        "zh", threshold=0.0, pricer=pricer, models_for=_no_models, router=canvas.quote_route)
    priced_tier = seen[0][1].get("resolution") or default
    assert priced_tier == submitted
    expected_amount = 0.117 if submitted == "2k" else 0.072
    assert quote is not None and quote.lines[0].amount == expected_amount


@pytest.mark.parametrize("shape_name", list(_PAYLOAD_SHAPES))
async def test_build_payload_byte_identical_to_main_88cbd358(shape_name):
    """build_payload output is byte-identical to main 88cbd358 (no auto-upgrade from a size string)."""
    pinned = skill_pin("clothing-swap")["model"]
    schema = wavespeed._schema(CATALOG[pinned])
    inputs = {**_PAYLOAD_BASE, **_PAYLOAD_SHAPES[shape_name]}
    current = await wavespeed.build_payload(None, schema, dict(inputs), pinned)
    main = await _main_wavespeed().build_payload(None, schema, dict(inputs), pinned)
    cur_bytes = json.dumps(current, sort_keys=True, separators=(",", ":")).encode()
    main_bytes = json.dumps(main, sort_keys=True, separators=(",", ":")).encode()
    assert cur_bytes == main_bytes
    # size-only / none must not grow a resolution key (WaveSpeed default 1k)
    if shape_name in ("size-only", "none"):
        assert "resolution" not in current
