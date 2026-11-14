"""Helpers for youtube-channel-banner ask cards.

Card 1 (#949 / HOLD #998) is one scrolling card (all questions page 1).
Card 2 (#934) is one question per page with Next.
"""
from __future__ import annotations

import asyncio

from test_skill_param_guard_e2e_956_957 import LOC


def is_submit_label(text: str, loc=LOC) -> bool:
    return loc["zh"]["chatMessage.submit"] in text or loc["en"]["chatMessage.submit"] in text


async def wait_dock(pg, timeout=25000):
    card = pg.locator('[data-testid="question-dock"] .ca-q')
    await card.wait_for(timeout=timeout)
    return card


async def read_page(card) -> dict:
    blocks = card.locator(".ca-q__block")
    count = await blocks.count()
    prompts = [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()]
    labels, placeholders, descs, thumbs = [], [], [], []
    selected = []
    for i in range(count):
        b = blocks.nth(i)
        labels.append([t.strip() for t in await b.locator(".ca-q__text").all_inner_texts()])
        inp = b.locator("input.ca-q__input")
        placeholders.append(await inp.get_attribute("placeholder") if await inp.count() else None)
        descs.append([t.strip() for t in await b.locator('[data-testid="ask-option-desc"]').all_inner_texts()])
        thumbs.append(await b.locator('[data-testid="ask-option-thumb"]').evaluate_all(
            "els => els.map(e => e.getAttribute('src') || '')"
        ))
        selected.append(await b.locator(".ca-q__opt[data-on]").count())
    return {
        "block_count": count,
        "prompts": prompts,
        "labels": labels,
        "placeholders": placeholders,
        "descs": descs,
        "thumbs": thumbs,
        "selected": selected,
        "head": await card.locator(".ca-q__head").inner_text(),
        "submit": (await card.locator(".ca-q__submit").text_content() or "").strip(),
        "scroll_card": await card.get_attribute("data-scroll-card"),
        "chevrons_disabled": (
            await card.locator(".ca-q__chev").count() == 2
            and await card.locator(".ca-q__chev").nth(0).is_disabled()
            and await card.locator(".ca-q__chev").nth(1).is_disabled()
        ),
    }



async def select_on_page(card, pick: int) -> None:
    """Click a choice option, or type into a text-only / other row so the page is filled."""
    block = card.locator(".ca-q__block").nth(0)
    opts = block.locator(".ca-q__opt")
    buttons = block.locator("button.ca-q__opt")
    n_btns = await buttons.count()
    if n_btns == 0:
        inp = block.locator("input.ca-q__input").first
        await inp.click()
        await inp.fill("ok")
        return
    if pick < n_btns:
        await buttons.nth(pick).click()
        return
    inp = opts.nth(pick).locator("input.ca-q__input")
    await inp.click()
    await inp.fill("ok")


async def _wait_prompt_change(card, previous: str, timeout_s: float = 5) -> None:
    for _ in range(int(timeout_s / 0.1)):
        now = [t.strip() for t in await card.locator(".ca-q__prompt").all_inner_texts()]
        if now and now[0] != previous:
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f"ask card did not advance from {previous!r}")


async def inspect_pages(pg, n_pages: int, loc=LOC) -> list[dict]:
    """Snapshot each page. Clicks option A only to enable Next; does not submit the last page."""
    card = await wait_dock(pg)
    submit = card.locator(".ca-q__submit")
    pages = []
    for i in range(n_pages):
        snap = await read_page(card)
        pages.append(snap)
        assert snap["block_count"] == 1, snap
        if i == n_pages - 1:
            break
        await select_on_page(card, 0)
        assert not is_submit_label(await submit.inner_text(), loc), await submit.inner_text()
        prev = snap["prompts"][0] if snap["prompts"] else ""
        await submit.click()
        await _wait_prompt_change(card, prev)
    return pages


async def inspect_and_answer(pg, picks, loc=LOC) -> list[dict]:
    """Snapshot each page, select picks[i], then Next / Submit on the last page."""
    card = await wait_dock(pg)
    submit = card.locator(".ca-q__submit")
    pages = []
    for i, pick in enumerate(picks):
        snap = await read_page(card)
        pages.append(snap)
        assert snap["block_count"] == 1, snap
        await select_on_page(card, pick)
        text = await submit.inner_text()
        last = i == len(picks) - 1
        if last:
            assert is_submit_label(text, loc), text
        else:
            assert not is_submit_label(text, loc), text
        prev = snap["prompts"][0] if snap["prompts"] else ""
        await submit.click()
        if not last:
            await _wait_prompt_change(card, prev)
    return pages


async def _scroll_block_into_card_body(block) -> None:
    """Scroll an in-card overflow body so the question is clickable (not just the page)."""
    await block.evaluate(
        """el => {
          const body = el.closest('.ca-q__body') || el.closest('[data-testid="question-body"]');
          if (!body) { el.scrollIntoView({block: 'nearest'}); return; }
          const er = el.getBoundingClientRect();
          const br = body.getBoundingClientRect();
          if (er.bottom > br.bottom) body.scrollTop += (er.bottom - br.bottom) + 16;
          if (er.top < br.top) body.scrollTop -= (br.top - er.top) + 16;
        }"""
    )


async def select_on_block(card, block_index: int, pick: int) -> None:
    """Like select_on_page, but on .ca-q__block[block_index] (scroll cards)."""
    block = card.locator(".ca-q__block").nth(block_index)
    await _scroll_block_into_card_body(block)
    opts = block.locator(".ca-q__opt")
    buttons = block.locator("button.ca-q__opt")
    n_btns = await buttons.count()
    if n_btns == 0:
        inp = block.locator("input.ca-q__input").first
        await inp.click()
        await inp.fill("ok")
    elif pick < n_btns:
        await buttons.nth(pick).click(force=True)
    else:
        inp = opts.nth(pick).locator("input.ca-q__input")
        await inp.click()
        await inp.fill("ok")
    # Wait until this question has an active selection (or filled other).
    for _ in range(25):
        if await block.locator(".ca-q__opt[data-on]").count():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"block {block_index} did not take pick {pick}")


async def inspect_scroll_card(pg, n_questions: int = 3, loc=LOC) -> dict:
    """Snapshot a scrolling ask card. All questions are in the DOM; Next does not page."""
    card = await wait_dock(pg)
    snap = await read_page(card)
    assert snap["scroll_card"] is not None, snap
    assert snap["block_count"] == n_questions, snap
    assert snap["chevrons_disabled"] is True, snap
    # Header chrome stays 1 of N — clicking Next/scroll must not become 2 of N.
    head = snap["head"]
    import re
    assert re.search(rf"1\s*(of|/)\s*{n_questions}", head), head
    assert not re.search(rf"2\s*(of|/)\s*{n_questions}", head), head
    return snap


async def answer_scroll_card(pg, picks, loc=LOC) -> dict:
    """Fill every question on a scrolling card and submit once. Does not paginate."""
    card = await wait_dock(pg)
    snap = await inspect_scroll_card(pg, n_questions=len(picks), loc=loc)
    for i, pick in enumerate(picks):
        await select_on_block(card, i, pick)
    unfilled = []
    for i in range(len(picks)):
        if not await card.locator(".ca-q__block").nth(i).locator(".ca-q__opt[data-on]").count():
            unfilled.append(i)
    assert not unfilled, f"scroll card questions still unfilled: {unfilled}"
    body = card.locator('[data-testid="question-body"]')
    if await body.count():
        await body.evaluate("el => { el.scrollTop = el.scrollHeight }")
    submit = card.locator(".ca-q__submit")
    for _ in range(12):
        text = (await submit.text_content() or "").strip()
        if is_submit_label(text, loc):
            break
        if await submit.is_enabled():
            await submit.click()
        if await body.count():
            await body.evaluate("el => { el.scrollTop = el.scrollHeight }")
        await asyncio.sleep(0.1)
    text = (await submit.text_content() or "").strip()
    assert is_submit_label(text, loc), text
    assert await submit.is_enabled(), "submit stayed disabled after every question was filled"
    # Still one scrolling card after filling — Next did not paginate.
    assert await card.get_attribute("data-scroll-card") is not None
    assert await card.locator(".ca-q__block").count() == len(picks)
    import re
    head = await card.locator(".ca-q__head").inner_text()
    assert re.search(rf"1\s*(of|/)\s*{len(picks)}", head), head
    await submit.click()
    return snap
