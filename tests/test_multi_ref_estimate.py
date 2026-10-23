"""#192: an image edit is quoted for the number of reference images it submits (WaveSpeed charges per extra reference,
e.g. gpt-image-2.5 sunburst +$0.015 each), so the quote equals the charge for 1, 2 and 3 references and grows with them.
Mocks only: no network, no charge."""
from __future__ import annotations

import pytest

from test_wavespeed import EDIT, _input_png, wavespeed, ws  # noqa: F401  (fixtures)


def per_ref(inputs: dict) -> float:
    # mock price API modelled on sunburst/edit 1k medium: $0.024 + $0.015 per reference image
    return round(0.024 + 0.015 * len(inputs.get("images") or []), 4)


def job(n: int) -> dict:
    refs = [_input_png(f"r{i}.png") for i in range(n)]
    return {"feature": "edit_image", "model": EDIT, "prompt": "blend", "image": refs[0], "images": refs[1:], "confirmed": True}


@pytest.mark.parametrize("n", [1, 2, 3])
async def test_quote_equals_charge_per_reference_count(ws, n):
    ws["prices"][EDIT] = per_ref
    est = await wavespeed.estimate(job(n))
    await wavespeed.submit(job(n))
    _, payload = ws["submits"][-1]
    assert len(payload["images"]) == n
    assert est["source"] == "quote" and est["price"] == pytest.approx(per_ref(payload))
    assert len(ws["quotes"][0]["inputs"]["images"]) == n


async def test_quote_grows_with_references(ws):
    ws["prices"][EDIT] = per_ref
    prices = [(await wavespeed.estimate(job(n)))["price"] for n in (1, 2, 3)]
    assert prices == pytest.approx([0.039, 0.054, 0.069])


async def test_quote_caps_references_at_max_items(ws):
    # the mock EDIT schema takes at most 3 images; submit drops the rest, so the quote does too
    ws["prices"][EDIT] = per_ref
    est = await wavespeed.estimate(job(5))
    await wavespeed.submit(job(5))
    assert len(ws["submits"][-1][1]["images"]) == 3 and est["price"] == pytest.approx(0.069)


async def test_no_reference_quote_sends_no_images(ws):
    ws["prices"][EDIT] = per_ref
    await wavespeed.estimate({"feature": "edit_image", "model": EDIT, "prompt": "x"})
    assert "images" not in ws["quotes"][0]["inputs"]
