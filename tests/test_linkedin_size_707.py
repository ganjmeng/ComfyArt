"""#707 size compatibility: requested pixels, the payload the adapter would submit,
and the pixels a provider file would deliver are three different facts.

The catalog fixture supplies schemas. No WaveSpeed HTTP and no new image file.
A 1584×396 provider file in one test is an explicit mock standing in for the
already-authorized Qwen check; this file does not re-run that check.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from pathlib import Path

import pytest

from ComfyArt.api import paid_guard, wavespeed
from ComfyArt.api.mcp_tools import canvas
from ComfyArt.api.mcp_tools._context import GUARD_CHAT_ID
from ComfyArt.api.skill_size import (
    VERIFIED, accepts_exact_pixels, audit_file, linkedin_decision, provider_submit, reconcile,
)
from ComfyArt.api.wavespeed import _schema

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/wavespeed_catalog_subset.json").read_text(encoding="utf-8"))
FLARE = "openai/gpt-image-2.5-flare/text-to-image"
DEFAULT_T2I = "openai/gpt-image-2.6-flare/text-to-image"
QWEN = VERIFIED["text_to_image"]
QWEN_EDIT = VERIFIED["image_edit"]
SENT: list[tuple[str, dict]] = []
# Recorded from a read-only GET of the live WaveSpeed catalog. Unit tests never
# fetch that endpoint; re-check with scripts/check_wavespeed_fixture.py (not CI).
# /edit size is x-hidden; /text-to-image size is visible and has a default.
LIVE_QWEN20_SIZE = {
    QWEN_EDIT: {
        "description": "Image dimensions in width*height format (e.g., 1024*1024, 1280*720)",
        "maximum": 4096,
        "minimum": 256,
        "type": "string",
        "x-hidden": True,
    },
    QWEN: {
        "default": "1024*1024",
        "description": "Image dimensions in width*height format (e.g., 1024*1024, 1280*720)",
        "maximum": 4096,
        "minimum": 256,
        "type": "string",
    },
}


def _flare():
    return _schema(FIXTURE[FLARE])


def _qwen():
    return _schema(FIXTURE[QWEN])


def test_flare_snaps_and_qwen_schema_submits_exact_size():
    flare = provider_submit(_flare(), 1584, 396)
    assert flare.get("aspect_ratio") == "3:1"
    assert flare.get("resolution") == "2k"
    assert "size" not in flare
    assert accepts_exact_pixels(_flare(), 1584, 396) is False
    # A prompt that merely mentions 1584x396 does not make this payload exact.
    assert "1584*396" not in json.dumps(flare)
    qwen = provider_submit(_qwen(), 1584, 396)
    assert qwen == {"size": "1584*396"}
    assert accepts_exact_pixels(_qwen(), 1584, 396) is True
    broken = {"properties": {"prompt": {}}}
    assert accepts_exact_pixels(broken, 1584, 396) is False


def test_delivery_follows_provider_pixels_not_the_request():
    # Mock file sizes only. Nothing here opens an image or calls a provider.
    same = reconcile((1584, 396), (1584, 396))
    assert same["requested"] == {"width": 1584, "height": 396}
    assert same["provider_output"] == same["delivered"] == {"width": 1584, "height": 396}
    assert same["match"] is True
    snapped = reconcile((1584, 396), (2048, 682))
    assert snapped["requested"]["width"] == 1584
    assert snapped["delivered"] == {"width": 2048, "height": 682}
    assert snapped["match"] is False
    assert reconcile((1584, 396), None)["delivered"] is None


def test_auto_uses_qwen_only_while_its_schema_accepts_exact_size():
    cfg = wavespeed.load_config()
    choice = linkedin_decision(
        {"prompt": "LinkedIn banner with the words Data", "skill": "linkedin-banner", "width": 1584, "height": 396},
        FIXTURE, cfg)
    assert "block" not in choice
    assert choice["args"]["model"] == QWEN
    assert choice["args"]["size_lock"] is True
    assert choice["args"]["size_candidates"] == [QWEN]
    assert "auto_model" not in choice["args"]
    assert choice["choice"]["provider_submit"] == {"size": "1584*396"}
    # Schema no longer accepts exact size: do not keep the id, and do not snap to flare.
    bare = json.loads(json.dumps(FIXTURE))
    bare[QWEN]["api_schema"]["api_schemas"][0]["request_schema"]["properties"].pop("size")
    refused = linkedin_decision(
        {"prompt": "banner", "skill": "linkedin-banner", "width": 1584, "height": 396}, bare, cfg)
    assert refused["block"]["submitted"] is False
    assert refused["block"]["model"] == ""
    assert QWEN not in refused["block"]["note"]
    assert "1584" in refused["block"]["note"]


def test_named_flare_is_refused_before_submit():
    cfg = wavespeed.load_config()
    got = linkedin_decision(
        {"prompt": "banner 1584x396", "skill": "linkedin-banner", "model": FLARE, "width": 1584, "height": 396},
        FIXTURE, cfg)
    block = got["block"]
    assert block["submitted"] is False and block["status"] == "failed"
    assert block["model"] == FLARE
    assert block["requested_size"] == {"width": 1584, "height": 396}
    assert block["provider_submit"]["aspect_ratio"] == "3:1"
    assert block["provider_output"] is None and block["delivered_size"] is None
    assert "没有提交" in block["note"] and "没有换模型" in block["note"]
    assert "1584*396" not in json.dumps(block["provider_submit"])


def test_other_skills_and_plain_banner_keep_the_table():
    # #825: banner/poster keywords hit poster_text -> 2.6 Flare; feature default is also flare
    plain = canvas._auto_choice("generate_image", {"prompt": "LinkedIn banner for a data engineer"})
    assert plain["model"] == DEFAULT_T2I and plain["category"] == "poster_text"
    poster = canvas._auto_choice("generate_image", {"prompt": "Movie poster with the headline SUMMER"})
    assert poster["model"] == DEFAULT_T2I and poster["category"] == "poster_text"
    cfg = wavespeed.load_config()
    assert cfg["features"]["text_to_image"]["default"] == DEFAULT_T2I
    # Qwen 2.0 stays off the Lovart dropdown. The skill path uses it only when the schema accepts the size.
    assert QWEN not in cfg["features"]["text_to_image"]["recommended"]
    assert QWEN not in [m["id"] for m in cfg["features"]["text_to_image"]["models"]]


@pytest.fixture
def relay(monkeypatch):
    SENT.clear()

    async def submit(action, args, project, timeout, chat=""):
        SENT.append((action, dict(args)))
        return {"ids": ["shape:g1"], "model": args.get("model") or args.get("edit_model")}

    async def catalog(refresh=False):
        return FIXTURE

    async def no_approval(label):
        return None

    monkeypatch.setattr(canvas, "submit_command", submit)
    monkeypatch.setattr(canvas, "maybe_ask_run_approval", no_approval)
    monkeypatch.setattr(wavespeed, "catalog", catalog)


def _run(tool, **args):
    chat = paid_guard.noturn_key(f"size-{uuid.uuid4().hex}")
    token = GUARD_CHAT_ID.set(chat)
    try:
        return asyncio.run(canvas.TOOLS[tool]["handler"](args))
    finally:
        GUARD_CHAT_ID.reset(token)
        paid_guard.TURNS.pop(chat, None)


def test_relay_auto_submits_qwen_and_does_not_claim_a_file(relay):
    out = _run("generate_image", prompt="Professional LinkedIn banner, headline in quotes", skill="linkedin-banner")
    assert SENT and SENT[0][0] == "generate_image"
    sent = SENT[0][1]
    assert sent["model"] == QWEN
    assert sent["width"] == 1584 and sent["height"] == 396 and sent["size_lock"] is True
    assert sent.get("model") != FLARE
    assert out["provider_submit"] == {"size": "1584*396"}
    assert out["requested_size"] == {"width": 1584, "height": 396}
    assert out["provider_output"] is None and out["delivered_size"] is None
    assert out["model_choice"]["model"] == QWEN
    assert "1584" in out["model_choice"]["note"]


def test_relay_named_flare_does_not_submit(relay):
    out = _run("generate_image", prompt="banner", skill="linkedin-banner", model=FLARE, width=1820, height=1024)
    assert SENT == []
    assert out["submitted"] is False
    assert out["requested_size"] == {"width": 1584, "height": 396}  # skill size replaces the invented 1820×1024
    assert out["provider_submit"]["aspect_ratio"] == "3:1"
    assert out["provider_output"] is None


def test_relay_refs_use_the_edit_schema_not_flare(relay):
    out = _run("generate_image", prompt="banner", skill="linkedin-banner", refs=["shape:face"])
    assert SENT[0][1]["edit_model"] == QWEN_EDIT
    assert SENT[0][1].get("model") != FLARE
    assert out["provider_submit"] == {"size": "1584*396"}
    assert accepts_exact_pixels(_schema(FIXTURE[QWEN_EDIT]), 1584, 396, QWEN_EDIT)


def test_fixture_qwen20_size_keeps_live_x_hidden():
    """Fail if the catalog fixture regresses to a bare `size: {}` (tests would pass for the wrong reason).

    Does not call WaveSpeed. `wavespeed-ai/qwen-image-2.0/edit` size must stay x-hidden, matching live.
    """
    assert set(LIVE_QWEN20_SIZE) == set(wavespeed.HIDDEN_SIZE_ALLOWLIST) == {QWEN_EDIT, QWEN}
    for mid, expected in LIVE_QWEN20_SIZE.items():
        got = _schema(FIXTURE[mid])["properties"]["size"]
        assert got == expected, f"{mid} fixture size drifted from the recorded live shape"
    assert _schema(FIXTURE[QWEN_EDIT])["properties"]["size"].get("x-hidden") is True


def test_hidden_size_allowlist_only_covers_qwen_image_20():
    """Live catalog marks qwen-image-2.0/edit size as x-hidden. Only the two allowlisted ids may submit it."""
    hidden = {"properties": {"size": {
        "type": "string", "minimum": 256, "maximum": 4096, "x-hidden": True,
        "description": "Image dimensions in width*height format (e.g., 1024*1024, 1280*720)",
    }}}
    other = "bytedance/seedream-v5.0-pro/edit"
    assert wavespeed.HIDDEN_SIZE_ALLOWLIST == frozenset({QWEN_EDIT, QWEN})
    assert provider_submit(hidden, 1584, 396) == {}
    assert accepts_exact_pixels(hidden, 1584, 396) is False
    assert provider_submit(hidden, 1584, 396, other) == {}
    assert accepts_exact_pixels(hidden, 1584, 396, other) is False
    assert provider_submit(hidden, 1584, 396, QWEN_EDIT) == {"size": "1584*396"}
    assert accepts_exact_pixels(hidden, 1584, 396, QWEN_EDIT) is True
    assert provider_submit(hidden, 1024, 1280, QWEN) == {"size": "1024*1280"}
    assert accepts_exact_pixels(hidden, 1024, 1824, QWEN) is True
    # Visible size still submits without being on the allowlist.
    visible = {"properties": {"size": {"type": "string", "minimum": 256, "maximum": 4096}}}
    assert provider_submit(visible, 1584, 396, other) == {"size": "1584*396"}


@pytest.mark.parametrize("skill,w,h", [
    ("linkedin-banner", 1584, 396),
    ("before-after", 1024, 1280),
    ("game-art", 1024, 1824),
])
def test_relay_exact_skills_with_refs_submit_qwen_edit_size(relay, skill, w, h):
    """#828 exact-size skills with a reference image go through generate_image and submit W*H on the edit model."""
    out = _run("generate_image", prompt="skill canvas with a reference", skill=skill, refs=["shape:face"])
    assert SENT and SENT[-1][0] == "generate_image"
    sent = SENT[-1][1]
    assert sent["edit_model"] == QWEN_EDIT
    assert sent.get("model") != FLARE
    assert sent["size_lock"] is True and sent["size_candidates"] == [QWEN_EDIT]
    assert sent["width"] == w and sent["height"] == h
    assert out["provider_submit"] == {"size": f"{w}*{h}"}
    assert out["model_choice"]["model"] == QWEN_EDIT
    assert out["submitted"] is not False


def test_relay_non_allowlisted_hidden_size_is_blocked(relay, monkeypatch):
    mid = "example/not-allowlisted/edit"
    catalog = json.loads(json.dumps(FIXTURE))
    catalog[mid] = {
        "api_schema": {"api_schemas": [{"request_schema": {"properties": {
            "images": {"maxItems": 3},
            "prompt": {},
            "size": {"type": "string", "minimum": 256, "maximum": 4096, "x-hidden": True},
        }}}]},
        "model_id": mid,
        "name": mid,
    }

    async def catalog_fn(refresh=False):
        return catalog

    monkeypatch.setattr(wavespeed, "catalog", catalog_fn)
    out = _run("generate_image", prompt="banner", skill="linkedin-banner", model=mid, refs=["shape:face"])
    assert SENT == []
    assert out["submitted"] is False
    assert out["model"] == mid
    assert "size" not in (out.get("provider_submit") or {})
    assert "没有提交" in (out.get("note") or out.get("error") or "")


def test_build_payload_sends_allowlisted_hidden_size_only():
    hidden_size = {"type": "string", "minimum": 256, "maximum": 4096, "x-hidden": True}
    schema = {"properties": {
        "prompt": {"type": "string"},
        "size": hidden_size,
        "foo": {"type": "string", "x-hidden": True},
    }}
    inputs = {"prompt": "banner", "width": 1584, "height": 396}
    allowed = asyncio.run(wavespeed.build_payload(None, schema, inputs, QWEN_EDIT))
    assert allowed["size"] == "1584*396"
    assert allowed["prompt"] == "banner"
    assert "foo" not in allowed  # allowlist is only for size, not every hidden field
    blocked = asyncio.run(wavespeed.build_payload(None, schema, inputs, "bytedance/seedream-v5.0-pro/edit"))
    assert "size" not in blocked
    assert "foo" not in blocked
    # text-to-image is also allowlisted if its size is later marked hidden
    t2i = asyncio.run(wavespeed.build_payload(None, schema, {"prompt": "x", "width": 1024, "height": 1824}, QWEN))
    assert t2i["size"] == "1024*1824"


@pytest.mark.parametrize("skill,w,h", [
    ("pose-fission", 1536, 2048),
    ("game-art", 1024, 1824),
])
def test_relay_pose_and_game_use_exact_size_not_flare(relay, skill, w, h):
    out = _run("generate_image", prompt="skill canvas", skill=skill)
    sent = SENT[-1][1]
    assert sent["model"] == QWEN and sent.get("model") != FLARE
    assert sent["size_lock"] is True and sent["size_candidates"] == [QWEN]
    assert sent["width"] == w and sent["height"] == h
    assert out["model_choice"]["model"] == QWEN
    assert out["provider_submit"] == {"size": f"{w}*{h}"}


def test_relay_before_after_uses_exact_size_not_flare(relay):
    out = _run("generate_image", prompt="beauty before after comparison banner", skill="before-after")
    assert SENT
    sent = SENT[-1][1]
    assert sent["model"] == QWEN and sent.get("model") != FLARE
    assert sent["size_lock"] is True and sent["size_candidates"] == [QWEN]
    assert sent["width"] == 1024 and sent["height"] == 1280
    assert out["model_choice"]["model"] == QWEN
    assert out["model_choice"]["category"] == "skill_size"
    assert out["provider_submit"] == {"size": "1024*1280"}


def test_size_lock_model_submits_without_joining_the_dropdown():
    with pytest.raises(wavespeed.WaveSpeedError):
        wavespeed.resolve_model("text_to_image", QWEN)
    assert wavespeed.resolve_model("text_to_image", QWEN, size_lock=True) == QWEN
    with pytest.raises(wavespeed.WaveSpeedError):
        wavespeed.resolve_model("text_to_image", "made/up-model", size_lock=True)
    cfg = wavespeed.load_config()
    assert QWEN not in [m["id"] for m in cfg["features"]["text_to_image"]["models"]]
    assert cfg["features"]["text_to_image"]["default"] == DEFAULT_T2I


def _png(w: int, h: int) -> bytes:
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def test_audit_file_reads_bytes_then_reconciles():
    ok = audit_file(_png(1584, 396), (1584, 396))
    assert ok["match"] is True and ok["error"] is None
    assert ok["requested"] == ok["provider_output"] == ok["delivered"] == {"width": 1584, "height": 396}
    bad = audit_file(_png(2048, 682), (1584, 396))
    assert bad["match"] is False and bad["read_error"] is False
    assert bad["provider_output"] == {"width": 2048, "height": 682}
    assert bad["delivered"] == bad["provider_output"]
    assert "2048×682" in bad["error"] and bad["error"].startswith("没有通过：")
    dead = audit_file(b"NOTPNG", (1584, 396))
    assert dead["read_error"] is True and dead["provider_output"] is None and dead["delivered"] is None
    assert "读不出像素" in dead["error"]
    # The same three facts stay distinct from a request that merely named the size.
    assert reconcile((1584, 396), (2048, 682))["match"] is False


def test_size_lock_preference_cases():
    """Not-in-dropdown is allowed. An unchecked model is not forced on. No candidate left means nothing submitted."""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--disable-warning=ExperimentalWarning",
         str(ROOT / "tests/js/size_lock_pref_run.ts")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    got = json.loads(proc.stdout)
    qwen = QWEN
    seedream = "bytedance/seedream-v5.0-lite/text-to-image"
    assert got["absent"] == {"ok": True, "model": qwen, "reason": "not_in_dropdown"}
    assert got["disabled"] == {"ok": False, "reason": "disabled"}
    assert got["allDisabled"] == {"ok": False, "reason": "disabled"}
    assert got["keepsOther"] == {"ok": True, "model": seedream, "reason": "checked"}
    assert got["keepsOther"]["model"] != qwen
    assert got["permittedOffDropdown"] == {"ok": True, "model": qwen, "reason": "checked"}
    assert "没有可用的尺寸兼容模型" in got["refused"] and got["refused"].startswith("没有提交：")
    assert got["refusedKept"] is True
    assert "默认模型" in got["refused"]
    assert got["match"] is None
    assert "2048×682" in got["mismatch"] and "1584×396" in got["mismatch"] and got["mismatchKept"] is True
    assert "读不出像素" in got["unread"] and got["unreadKept"] is True
    assert got["placed"] == got["mismatch"]
    assert got["quiet"] is None
    bot = (ROOT / "src/botCommands.ts").read_text(encoding="utf-8")
    gate = bot.split("async function startGenerator", 1)[1].split("const id = createGenerator", 1)[0]
    assert "pickSizeModel(" in gate and "SIZE_LOCK_REFUSED" in gate
    assert "const locked: ModelDef | undefined = lockId" not in bot
    gen = (ROOT / "src/generate.ts").read_text(encoding="utf-8")
    assert "size_lock: true" in gen
    poll = (ROOT / "api/wavespeed.py").read_text(encoding="utf-8")
    body = poll.split("async def _poll_once", 1)[1].split("\nasync def ", 1)[0]
    assert "_audit_locked_files(job, refs)" in body and "audit_file(" in poll
    assert "isOwnSizeError(msg)" in (ROOT / "src/wsErrors.ts").read_text(encoding="utf-8")
    assert "lockedDeliveryError(holder.meta, media)" in (ROOT / "src/jobs.ts").read_text(encoding="utf-8")
    assert wavespeed.load_config()["features"]["text_to_image"]["default"] == DEFAULT_T2I


def test_failed_banner_is_not_retried_on_flare(relay):
    out = _run("generate_image", prompt="banner", skill="linkedin-banner", fallback_for=QWEN)
    assert SENT == []
    assert out["submitted"] is False
    assert FLARE not in out["note"]
    assert "没有提交" in out["note"]
