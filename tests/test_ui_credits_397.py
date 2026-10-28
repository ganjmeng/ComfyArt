"""#397: quote card / cloud confirm / settings confirm-line all show UI credits (not $).

Mocks only. Migrations and formatters are pure; HTTP confirm uses the aiohttp test client.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ROOT = Path(__file__).resolve().parent.parent
node = pytest.mark.skipif(
    not (ROOT / "node_modules" / ".bin" / "rolldown").exists() or not shutil.which("node"),
    reason="needs node + npm install",
)

ZH = json.loads((ROOT / "src/locales/zh.json").read_text())
EN = json.loads((ROOT / "src/locales/en.json").read_text())


# --- shared formatter ------------------------------------------------------------------

@pytest.mark.parametrize("usd,want", [
    (0, 0),
    (0.004, 1),
    (0.01, 1),
    (0.04, 4),
    (0.29999, 30),
    (0.30000001, 30),
    (0.300001, 31),
    (0.5, 50),
    (0.64, 64),
    (1.14, 114),
    (12.5, 1250),
])
def test_ui_credits_ceil_rule(usd, want):
    from ComfyArt.bot.run_budget import ui_credits
    assert ui_credits(usd) == want


@node
def test_ui_credits_ts_matches_python(tmp_path):
    out = tmp_path / "c.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "ui_credits.ts"},
    )
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    from ComfyArt.bot.run_budget import ui_credits
    want = [ui_credits(x) for x in (0, 0.004, 0.29999, 0.30000001, 0.300001, 0.5, 0.64, 1.14)]
    assert got == want


# --- prefs migration without loss ------------------------------------------------------

def test_migrate_confirm_usd_to_credits_without_loss(tmp_path, monkeypatch):
    """Legacy wavespeed_prefs.json {confirm_usd: N} rewrites to confirm_credits = ui_credits(N)."""
    from ComfyArt.api import wavespeed
    from ComfyArt.bot.run_budget import ui_credits

    prefs = tmp_path / "wavespeed_prefs.json"
    monkeypatch.setattr(wavespeed, "app_path", lambda name: str(tmp_path / name))

    for usd in (0, 0.01, 0.5, 1, 0.004, 12.5, 1000):
        prefs.write_text(json.dumps({"confirm_usd": usd}))
        credits = wavespeed.confirm_credits()
        assert credits == ui_credits(usd), (usd, credits)
        # rewritten, no loss on second read
        stored = json.loads(prefs.read_text())
        assert stored == {"confirm_credits": credits}
        assert "confirm_usd" not in stored
        assert wavespeed.confirm_credits() == credits
        assert wavespeed.confirm_usd() == pytest.approx(credits / 100.0)


def test_confirm_credits_prefs_round_trip(tmp_path, monkeypatch):
    from ComfyArt.api import wavespeed
    monkeypatch.setattr(wavespeed, "app_path", lambda name: str(tmp_path / name))
    prefs = tmp_path / "wavespeed_prefs.json"
    prefs.write_text(json.dumps({"confirm_credits": 75}))
    assert wavespeed.confirm_credits() == 75
    assert wavespeed.confirm_usd() == pytest.approx(0.75)
    # already credits — not dirty, file unchanged
    assert json.loads(prefs.read_text()) == {"confirm_credits": 75}


def test_migrate_confirm_prefs_helper_cases():
    from ComfyArt.api.wavespeed import migrate_confirm_prefs, DEFAULT_CONFIRM_CREDITS
    from ComfyArt.bot.run_budget import ui_credits
    assert migrate_confirm_prefs({"confirm_credits": 40}) == (40, False)
    assert migrate_confirm_prefs({"confirm_usd": 0.5}) == (50, True)
    assert migrate_confirm_prefs({"confirm_usd": 0.004}) == (ui_credits(0.004), True)
    assert migrate_confirm_prefs({}) == (DEFAULT_CONFIRM_CREDITS, False)
    assert migrate_confirm_prefs({"confirm_usd": -1}) == (DEFAULT_CONFIRM_CREDITS, False)
    # confirm_credits wins over stale confirm_usd
    assert migrate_confirm_prefs({"confirm_credits": 10, "confirm_usd": 0.5}) == (10, False)


# --- locales / askCost / plan quote: no $ in UI ----------------------------------------

def test_cloud_confirm_locales_use_credits_not_dollars():
    for key in (
        "jobs.confirmCost", "jobs.confirmEstimate", "jobs.confirmEstimateTier",
        "jobs.confirmSegLeft", "jobs.confirmSegMax", "wsKey.confirmUsd",
    ):
        assert "$" not in ZH[key], (key, ZH[key])
        assert "$" not in EN[key], (key, EN[key])
    assert "积分" in ZH["jobs.confirmCost"] and "credits" in EN["jobs.confirmCost"]
    assert "积分" in ZH["wsKey.confirmUsd"] and "credits" in EN["wsKey.confirmUsd"]


def test_ask_cost_uses_ui_credits():
    comfy = (ROOT / "src/comfy.ts").read_text()
    ask = comfy[comfy.index("export function askCost"):comfy.index("export async function queuePrompt")]
    assert "uiCredits(price ?? 0)" in ask
    assert "usd(price" not in ask
    # mutation: dialog amount must come from uiCredits, not usd()
    assert "const p = String(uiCredits(price ?? 0))" in ask


async def test_plan_quote_prompt_is_credits_not_dollars():
    from ComfyArt.bot.plan_quote import build_quote
    from ComfyArt.bot.run_budget import ui_credits

    steps = [
        {"text": "生成海报", "tool": "generate_image", "model": "acme/poster-xl",
         "arguments": {"prompt": "p"}},
        {"text": "生成视频", "tool": "generate_video", "model": "acme/clip-hd",
         "arguments": {"prompt": "v", "duration": 5}},
    ]
    prices = {"acme/poster-xl": 0.04, "acme/clip-hd": 0.60}

    async def pricer(model, inputs):
        return prices.get(model)

    async def models_for(feature):
        return []

    zh = await build_quote(steps, "zh", threshold=0.5, pricer=pricer, models_for=models_for)
    en = await build_quote(steps, "en", threshold=0.5, pricer=pricer, models_for=models_for)
    assert zh is not None and en is not None
    assert zh.prompt == (
        f"这个任务共 2 步，预计约 {ui_credits(0.64)} 积分，"
        f"超过了你设置的 {ui_credits(0.5)} 积分确认线。确定开始吗？"
    )
    assert "$" not in zh.prompt and "$" not in en.prompt
    assert all("$" not in ln.price for ln in zh.lines)
    assert zh.total_text == "64 积分"
    # spend 0 → 「积分 0」
    from ComfyArt.bot.plan_quote import credits_label
    assert credits_label(0, "zh") == "积分 0"
    assert credits_label(0, "en") == "0 credits"
    assert credits_label(0.004, "zh") == "1 积分"


# --- mutations that go red if $ / wrong ceil returns -----------------------------------

def test_mutation_plan_quote_prompt_rejects_dollar_sign():
    """Would go red if _PROMPT or credits_label reintroduced $."""
    src = (ROOT / "bot/plan_quote.py").read_text()
    # the UI prompt templates must not embed $
    assert '"zh": "这个任务共 {n} 步，预计约 {total} 积分' in src
    assert "${total}" not in src and "${threshold}" not in src
    assert "credits_label" in src and "ui_credits(total)" in src


def test_mutation_settings_api_is_credits():
    src = (ROOT / "api/wavespeed.py").read_text()
    assert '"confirm_credits": confirm_credits()' in src
    assert 'json.dump({"confirm_credits": credits}, f)' in src
    # GET must not answer with confirm_usd as the settings field
    assert 'return web.json_response({"confirm_usd": confirm_usd()})' not in src


def test_mutation_key_settings_uses_credits_testid():
    ks = (ROOT / "src/ui/KeySettings.tsx").read_text()
    assert 'data-testid="ws-confirm-credits"' in ks
    assert "thresholdCredits" in ks and "getConfirmCredits" in ks
    assert "thresholdUsd" not in ks
    assert "$" not in ZH["wsKey.confirmUsd"]


@node
def test_mutation_ui_credits_ceil_breaks_if_floor(tmp_path):
    """Would go red if TS uiCredits used floor / trunc instead of ceil."""
    out = tmp_path / "c.mjs"
    subprocess.run(
        [str(ROOT / "node_modules/.bin/rolldown"), "-c", "tests/js/rolldown.config.mjs"],
        cwd=ROOT, check=True, capture_output=True,
        env={**os.environ, "OUT": str(out), "ENTRY": "ui_credits.ts"},
    )
    got = json.loads(subprocess.run(["node", str(out)], check=True, capture_output=True, text=True).stdout)
    # $0.004 → 1 (ceil), not 0 (floor); $0.300001 → 31 not 30
    assert got[1] == 1 and got[4] == 31


# --- confirm HTTP API ------------------------------------------------------------------

@pytest.fixture
def prefs_dir(tmp_path, monkeypatch):
    from ComfyArt.api import wavespeed
    monkeypatch.setattr(wavespeed, "app_path", lambda name: str(tmp_path / name))
    return tmp_path


async def test_confirm_http_get_put_credits(prefs_dir):
    from ComfyArt.api import wavespeed
    import server
    app = web.Application()
    app.router.add_routes(server.PromptServer.instance.routes)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        assert (await (await client.get("/comfyart/wavespeed/confirm")).json()) == {"confirm_credits": 50}
        ok = await client.put("/comfyart/wavespeed/confirm", json={"confirm_credits": 80})
        assert ok.status == 200 and (await ok.json()) == {"confirm_credits": 80}
        assert wavespeed.confirm_credits() == 80 and wavespeed.confirm_usd() == pytest.approx(0.80)
        # legacy USD write still accepted and stored as credits
        legacy = await client.put("/comfyart/wavespeed/confirm", json={"confirm_usd": 0.5})
        assert legacy.status == 200 and (await legacy.json()) == {"confirm_credits": 50}
        stored = json.loads((prefs_dir / "wavespeed_prefs.json").read_text())
        assert stored == {"confirm_credits": 50}
    finally:
        await client.close()
