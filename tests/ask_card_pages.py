"""Helpers for one-question-per-page ask cards (youtube-channel-banner after #934)."""
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
        "submit": await card.locator(".ca-q__submit").inner_text(),
        "scroll_card": await card.get_attribute("data-scroll-card"),
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
