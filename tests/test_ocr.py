from __future__ import annotations


async def test_ocr_rejects_missing_and_invalid_sources(bot_client, fresh_user_dir):
    assert (await bot_client.post("/comfyart/ocr", json={})).status == 400
    assert (await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=nope.png&type=output"})).status == 404
    assert (await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=../../x.png&type=output"})).status == 404
