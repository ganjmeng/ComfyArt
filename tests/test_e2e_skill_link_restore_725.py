"""#725 e2e (mocks only, $0): old skill links restore refs to the composer, not the canvas;
draft + refs survive two refreshes without duplicates. Visible + hidden (e2e hide fixture)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from conftest import write_settings
from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401

pw = pytest.importorskip("playwright.async_api")
ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not any((ROOT / "dist").glob("*")), reason="needs built dist/")

NOTICE = '[data-testid="skill-hidden-notice"]'
CHIP = '[data-testid="composer-skill-chip"]'
CAPSULE = '[data-testid="composer-capsule"]'
CANVAS = '.tl-shape[data-shape-type="image"], .tl-shape[data-shape-type="video"]'
PAID = ("wavespeed", "kie.ai", "kie.com")
SEND = ("/bot/", "/send", "/generate")
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
    "0000001649444154789c63f8cfc0f09f8181e1ff7f0606000024f205fd1c5a4a5f0000000049454e44ae426082"
)
REF_FILES = ["r725a.png", "r725b.png"]
DRAFT = "keep725-draft"
SHOTS = os.environ.get("SHOTS_725")
LOC = {lg: json.loads((ROOT / f"src/locales/{lg}.json").read_text()) for lg in ("zh", "en")}


@pytest.fixture
def fake_agent(fake_provider):
    write_settings(**{"bot-provider": fake_provider.id, "enable-bot": True, "enable-mcp": True})
    return fake_provider


def _write_refs():
    import folder_paths
    inp = folder_paths.STATE["base"] / "input"
    inp.mkdir(parents=True, exist_ok=True)
    for n in REF_FILES:
        (inp / n).write_bytes(PNG)


def _ref_qs(n=2) -> str:
    return "".join(f"&ref=%2Fapi%2Fview%3Ffilename%3D{name}%26type%3Dinput" for name in REF_FILES[:n])


async def _page(p, lang="zh", theme="light", hide=None):
    browser = await p.chromium.launch()
    context = await browser.new_context(viewport={"width": 1440, "height": 900})
    pg = await context.new_page()
    hide_js = ""
    if hide:
        hide_js = (
            "localStorage.setItem('comfyart.e2e','1');"
            f"localStorage.setItem('comfyart.e2e.hideSkills','{hide}');"
        )
    await pg.add_init_script(
        f"localStorage.setItem('comfyart.lang','{lang}');"
        f"localStorage.setItem('comfyart.theme','{theme}');"
        + hide_js
    )
    return browser, pg


async def _dismiss(pg):
    for _ in range(3):
        if await pg.locator(".ca-modal").count():
            await pg.keyboard.press("Escape")
            await pg.wait_for_timeout(200)


async def _ready(pg):
    await pg.locator(".ca-composer__input").wait_for(timeout=30_000)
    await _dismiss(pg)
    await pg.wait_for_timeout(800)


async def _shot(pg, name: str):
    if not SHOTS:
        return
    Path(SHOTS).mkdir(parents=True, exist_ok=True)
    await pg.wait_for_timeout(400)
    await pg.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def _paid_or_send(urls: list[str]) -> list[str]:
    out = []
    for u in urls:
        low = u.lower()
        if any(k in low for k in PAID):
            out.append(u)
        elif any(k in u for k in ("wavespeed", "kie")):
            out.append(u)
    return out


def _auto_sends(urls: list[str]) -> list[str]:
    return [u for u in urls if u.endswith("/send") or "/generate" in u]


async def _state(pg) -> dict:
    return {
        "draft": await pg.locator(".ca-composer__input").input_value(),
        "capsules": await pg.locator(CAPSULE).count(),
        "loose": await pg.locator("[data-testid='composer-capsule'][data-loose]").count(),
        "canvas": await pg.locator(CANVAS).count(),
        "chip": await pg.locator(CHIP).count(),
        "notice": await pg.locator(NOTICE).count(),
    }


async def _reload_twice(pg):
    await pg.reload(wait_until="domcontentloaded")
    await _ready(pg)
    await pg.reload(wait_until="domcontentloaded")
    await _ready(pg)


async def test_e2e_725_visible_skill_refs_and_draft_composer_only(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC1 + AC4: visible skill, 2 refs + draft → composer 2, canvas 0, chip on, no auto-send; refresh twice stays."""
    _write_refs()
    reqs: list[str] = []
    async with pw.async_playwright() as p:
        browser, pg = await _page(p)
        pg.on("request", lambda r: reqs.append(r.url) if r.method != "GET" else None)
        await pg.goto(app_url + f"?project=p725vis&new=1&skill=yingzao&mode=agent&ask={DRAFT}{_ref_qs()}")
        await _ready(pg)
        st = await _state(pg)
        assert st["canvas"] == 0, st
        assert st["loose"] == 2 and st["capsules"] == 2, st
        assert st["draft"] == DRAFT, st
        assert st["chip"] == 1 and st["notice"] == 0, st
        name = LOC["zh"].get("skills.yingzao")
        if name:
            assert name in await pg.locator(".ca-composer").inner_text()
        await _shot(pg, "01-visible-restore")
        assert not _paid_or_send(reqs), reqs
        assert not _auto_sends(reqs), reqs
        assert mock_ws["submits"] == []
        await _reload_twice(pg)
        st2 = await _state(pg)
        assert st2 == st, (st, st2)
        await _shot(pg, "03-visible-after-2-refreshes")
        assert not _paid_or_send(reqs), reqs
        assert mock_ws["submits"] == []
        await browser.close()


async def test_e2e_725_hidden_skill_fixture_refs_composer_only(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC2 + AC4: e2e hide fixture on yingzao — notice, no chip, composer 2, canvas 0; refresh keeps notice + refs."""
    _write_refs()
    reqs: list[str] = []
    async with pw.async_playwright() as p:
        browser, pg = await _page(p, hide="yingzao")
        pg.on("request", lambda r: reqs.append(r.url) if r.method != "GET" else None)
        await pg.goto(app_url + f"?project=p725hid&new=1&skill=yingzao&mode=agent&ask={DRAFT}{_ref_qs()}")
        await _ready(pg)
        st = await _state(pg)
        assert st["canvas"] == 0, st
        assert st["loose"] == 2 and st["capsules"] == 2, st
        assert st["draft"] == DRAFT, st
        assert st["chip"] == 0 and st["notice"] == 1, st
        notice = LOC["zh"]["skills.hiddenUnavailable"]
        assert notice in await pg.locator(NOTICE).inner_text()
        await _shot(pg, "02-hidden-restore")
        assert not _paid_or_send(reqs), reqs
        assert not _auto_sends(reqs), reqs
        assert mock_ws["submits"] == []
        await _reload_twice(pg)
        st2 = await _state(pg)
        assert st2 == st, (st, st2)
        assert notice in await pg.locator(NOTICE).inner_text()
        await _shot(pg, "04-hidden-after-2-refreshes")
        assert not _paid_or_send(reqs), reqs
        await browser.close()


async def test_e2e_725_visible_ask_only_no_refs(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC3 + AC4: visible skill, ask only — composer refs 0, canvas 0, draft kept; refresh twice stays."""
    reqs: list[str] = []
    async with pw.async_playwright() as p:
        browser, pg = await _page(p)
        pg.on("request", lambda r: reqs.append(r.url) if r.method != "GET" else None)
        await pg.goto(app_url + f"?project=p725ask&new=1&skill=before-after&mode=agent&ask={DRAFT}")
        await _ready(pg)
        st = await _state(pg)
        assert st["canvas"] == 0 and st["capsules"] == 0 and st["loose"] == 0, st
        assert st["draft"] == DRAFT and st["chip"] == 1 and st["notice"] == 0, st
        assert not _paid_or_send(reqs) and not _auto_sends(reqs), reqs
        await _reload_twice(pg)
        assert await _state(pg) == st
        await browser.close()


async def test_e2e_725_visible_refs_only_no_ask(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC5: visible skill, refs only — composer 2, canvas 0, input empty; refresh twice no dupes."""
    _write_refs()
    async with pw.async_playwright() as p:
        browser, pg = await _page(p)
        await pg.goto(app_url + f"?project=p725ref&new=1&skill=yingzao&mode=agent{_ref_qs()}")
        await _ready(pg)
        st = await _state(pg)
        assert st["canvas"] == 0 and st["loose"] == 2 and st["capsules"] == 2, st
        assert st["draft"] == "" and st["chip"] == 1 and st["notice"] == 0, st
        await _reload_twice(pg)
        assert await _state(pg) == st
        await browser.close()


async def test_e2e_725_last_link_wins_nonskill_ask_ref(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC last-opened-link-wins: ?skill= then a non-skill ?ask=&ref= on the same project;
    after two refreshes the first link's draft/refs/chip must not come back."""
    _write_refs()
    async with pw.async_playwright() as p:
        browser, pg = await _page(p)
        await pg.goto(app_url + f"?project=p725win1&new=1&skill=yingzao&mode=agent&ask={DRAFT}{_ref_qs()}")
        await _ready(pg)
        st = await _state(pg)
        assert st["draft"] == DRAFT and st["loose"] == 2 and st["chip"] == 1, st
        # new non-skill link, same tab / same project
        await pg.goto(app_url + f"?project=p725win1&ask=nonskill725{_ref_qs(1)}")
        await _ready(pg)
        mid = await _state(pg)
        assert mid["draft"] != DRAFT, mid
        assert mid["loose"] == 0, mid
        assert mid["chip"] == 0, mid
        await _reload_twice(pg)
        after = await _state(pg)
        assert after["draft"] != DRAFT and DRAFT not in after["draft"], after
        assert after["loose"] == 0, after
        assert after["chip"] == 0 and after["notice"] == 0, after
        await _shot(pg, "05-skill-then-nonskill-refresh2")
        await browser.close()


async def test_e2e_725_last_link_wins_plain_home_then_project(app_url, mock_ws, fake_agent):  # noqa: F811
    """AC last-opened-link-wins: ?skill= then plain home `/`, then reopen the same project
    with no handoff params; the first link's draft/refs must not reappear, including after refresh."""
    _write_refs()
    async with pw.async_playwright() as p:
        browser, pg = await _page(p)
        await pg.goto(app_url + f"?project=p725win2&new=1&skill=yingzao&mode=agent&ask={DRAFT}{_ref_qs()}")
        await _ready(pg)
        st = await _state(pg)
        assert st["draft"] == DRAFT and st["loose"] == 2 and st["chip"] == 1, st
        await pg.goto(app_url)  # plain home, no project / no skill
        await pg.get_by_test_id("home-shell").wait_for(timeout=30_000)
        await pg.wait_for_timeout(400)
        await pg.goto(app_url + "?project=p725win2")
        await _ready(pg)
        reopened = await _state(pg)
        assert reopened["draft"] != DRAFT, reopened
        assert reopened["loose"] == 0, reopened
        assert reopened["chip"] == 0, reopened
        await _reload_twice(pg)
        after = await _state(pg)
        assert after["draft"] != DRAFT, after
        assert after["loose"] == 0 and after["chip"] == 0, after
        await _shot(pg, "06-skill-then-home-project-refresh2")
        await browser.close()
