"""#1019 mock e2e ($0): no-template brand path through three cards, three quotes, eight images.

Real dist, real ask cards, real quote card, real generate_image sizing. WaveSpeed is the
local mock. Nothing is paid.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from test_e2e_comment_edit import app_url, mock_ws  # noqa: F401
from test_skill_e2e_portrait_studio import ws_forward  # noqa: F401
from test_a_class_fullapp_e2e_911 import (  # noqa: F401
    _all_ids, _bind_open_project, _calls, _reply, _wait, built_dist, local_agent, no_paid_keys,
)
from test_template_output_e2e_979 import _open_template

pw = pytest.importorskip("playwright.async_api")

BRAND = "brand-identity-director"
BRIEF = "品牌名：栖木咖啡（QIMU COFFEE）。社区精品咖啡店，目标人群 25–35 岁城市白领，关键词：温暖、自然、手作。需要 logo 与基础品牌视觉系统。"
SHOTS = Path(os.environ.get("BRAND_1019_SHOTS", "/tmp/brand-1019-shots"))
DONE = (
    "本次交付清单：情绪板 1 张，Logo 方向 3 张，规范卡、外带杯、纸袋、门头各 1 张。\n"
    "如实说明的边界：物料上的标志是生图复现，正式使用需要矢量替换；色值为屏幕估算，不是 Pantone/CMYK。\n"
    "下一步建议：菜单板、社媒模板、名片。"
)


def _script(state):
    card1 = {"questions": [
        {"id": "bi_delivery", "prompt": "这次「基础品牌视觉系统」要交付哪些物料？",
         "options": [{"id": "A", "label": "核心"}, {"id": "B", "label": "菜单"}]},
        {"id": "bi_color", "prompt": "色彩方向选哪一种？",
         "options": [{"id": "A", "label": "暖土"}, {"id": "B", "label": "纯暖"}]},
        {"id": "bi_mark", "prompt": "Logo 的构成方向偏好？",
         "options": [{"id": "A", "label": "符号"}, {"id": "B", "label": "文字"}]},
        {"id": "bi_source", "prompt": "门店与产品素材怎么处理？",
         "options": [{"id": "A", "label": "生成"}, {"id": "B", "label": "上传"}]},
    ], "page_count": 4, "allow_skip": True}
    card2 = {"questions": [{"id": "bi_moodboard", "prompt": "这张情绪板可以作为后续全套物料的视觉基准吗？",
                            "options": [{"id": "A", "label": "通过"}, {"id": "B", "label": "重出"}]}],
             "allow_skip": True}
    card3 = {"questions": [{"id": "bi_direction", "prompt": "选定哪个 Logo 方向作为最终标识（logo_primary）？",
                            "options": [{"id": "A", "label": "方向 A", "recommended": True},
                                        {"id": "B", "label": "方向 B"}, {"id": "C", "label": "方向 C"}]}],
             "allow_skip": True}
    steps = [
        _calls(("ask_user", card1)),
        _calls(("generate_image", {"prompt": "3x3 moodboard for 栖木咖啡 QIMU COFFEE", "skill": BRAND})),
        None,  # wait, filled from the messages
        _calls(("ask_user", card2)),
        _calls(*(("generate_image", {"prompt": f"logo direction {i} for 栖木咖啡", "skill": BRAND}) for i in range(3))),
        None,
        _calls(("ask_user", card3)),
        _calls(*(("generate_image", {"prompt": f"{name} for 栖木咖啡 QIMU COFFEE", "skill": BRAND})
                 for name in ("spec card", "takeaway cup", "paper bag", "storefront"))),
        None,  # wait until the four deliverables are placed
        _reply(DONE),
    ]

    def respond(messages, n):
        state["messages"] = messages
        step = steps[min(n, len(steps) - 1)]
        if step is None:
            return _calls(("wait_generation", {"ids": _all_ids(messages)}))
        return step

    return respond


async def _shot(pg, name: str):
    SHOTS.mkdir(parents=True, exist_ok=True)
    await pg.screenshot(path=str(SHOTS / name), full_page=False)


async def _answer_pages(pg, pages: int):
    card = pg.locator(".ca-q").last
    await card.wait_for(timeout=30000)
    for _ in range(pages):
        opt = card.locator(".ca-q__block").locator(".ca-q__opt").first
        await opt.click()
        await card.locator(".ca-q__submit").click()


async def _confirm_quote(pg):
    ok = pg.get_by_test_id("chat-inline-confirm-ok")
    await ok.wait_for(timeout=30000)
    await ok.click()


async def test_default_path_cards_quotes_and_eight_images(app_url, mock_ws, local_agent, ws_forward):
    provider, state = local_agent
    state["respond"] = _script(state)
    async with pw.async_playwright() as p:
        browser, pg = await _open_template(p, app_url, "zh", BRAND, ws_forward, None, "user_requirement", BRIEF)
        try:
            await pg.locator(".ca-composer__input").click()
            await pg.wait_for_function(
                "() => { const b = document.querySelector('.ca-composer__slotwrap button[data-slot=send]');"
                " return b && !b.disabled; }", timeout=60000)
            await pg.locator(".ca-composer__input").press("Enter")
            await pg.locator(".ca-q").last.wait_for(timeout=30000)
            assert await pg.locator(".ca-q__opt[data-on]").count() == 0
            assert "推荐" not in await pg.locator(".ca-q").last.inner_text()
            assert "1 of 4" in await pg.locator(".ca-q__page").last.inner_text()
            await _shot(pg, "card1-default-zh.png")
            await _answer_pages(pg, 4)
            quote = pg.get_by_test_id("chat-inline-planquote").last
            await quote.wait_for(timeout=30000)
            await quote.scroll_into_view_if_needed()
            await _shot(pg, "quote-moodboard-zh.png")
            await _confirm_quote(pg)
            await _wait(lambda: any(a.get("brand_slot") == "moodboard" for _, a in state["mcp"] if isinstance(a, dict)), timeout=60)
            mood = [a for name, a in state["mcp"] if name == "generate_image" and a.get("brand_slot") == "moodboard"]
            assert (mood[0]["width"], mood[0]["height"]) == (2048, 1152)
            await pg.locator(".ca-q").last.wait_for(timeout=60000)
            await _shot(pg, "card2-moodboard-zh.png")
            await _answer_pages(pg, 1)
            await _confirm_quote(pg)
            await _wait(lambda: sum(1 for _, a in state["mcp"] if isinstance(a, dict) and str(a.get("brand_slot", "")).startswith("logo_")) >= 3, timeout=90)
            logos = [a for _, a in state["mcp"] if isinstance(a, dict) and str(a.get("brand_slot", "")).startswith("logo_")]
            assert [(a["width"], a["height"]) for a in logos[:3]] == [(2048, 2048)] * 3
            assert all(a.get("refs") for a in logos[:3])
            toast = pg.locator(".tlui-toast__container").filter(has_text="出图尺寸低于预期")
            await toast.first.wait_for(timeout=30000)
            await pg.wait_for_timeout(400)
            # One round of identical size notices is a single toast. An earlier
            # stage can still have its own toast on screen.
            assert 1 <= await toast.count() <= 2
            await _shot(pg, "toast-size-zh.png")
            await pg.locator(".ca-q").last.wait_for(timeout=60000)
            text = await pg.locator(".ca-q").last.inner_text()
            assert "推荐" in text
            assert await pg.locator(".ca-q__opt[data-on]").count() == 0
            await _shot(pg, "card3-direction-zh.png")
            await _answer_pages(pg, 1)
            quote = pg.get_by_test_id("chat-inline-planquote").last
            await quote.wait_for(timeout=30000)
            await quote.scroll_into_view_if_needed()
            quote_text = await quote.inner_text()
            assert "规范卡 1536×2048 3:4" in quote_text
            assert "外带杯与杯套 1536×2048 3:4" in quote_text
            assert "纸袋 1536×2048 3:4" in quote_text
            assert "门店门头 2048×1152 16:9" in quote_text
            assert "精确像素" not in quote_text
            assert "本次交付清单" not in await pg.locator(".ca-chat").inner_text()
            await _shot(pg, "quote-finals-zh.png")
            await _confirm_quote(pg)
            await _wait(lambda: sum(1 for _, a in state["mcp"] if isinstance(a, dict) and a.get("brand_slot") in {"spec", "cup", "bag", "storefront"}) >= 4, timeout=90)
            finals = [a for _, a in state["mcp"] if isinstance(a, dict) and a.get("brand_slot") in {"spec", "cup", "bag", "storefront"}]
            assert [(a["brand_slot"], a["width"], a["height"]) for a in finals[:4]] == [
                ("spec", 1536, 2048), ("cup", 1536, 2048), ("bag", 1536, 2048), ("storefront", 2048, 1152)]
            assert all(len(a.get("refs") or []) >= 1 for a in finals[:4])
            await _wait(lambda: any(DONE.splitlines()[0][:8] in str(m) for m in state.get("messages") or []), timeout=90)
            body = await pg.locator(".ca-chat").inner_text()
            assert "矢量替换" in body and "色值" in body and "可直接投产" not in body
            assert "已暂停" not in body and "任务卡住了" not in body
            assert body.find("1536×2048") < body.find("本次交付清单")
            await pg.locator(".ca-chat").locator("text=本次交付清单").last.scroll_into_view_if_needed()
            await _shot(pg, "final-canvas-zh.png")
        finally:
            await browser.close()
