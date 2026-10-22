from __future__ import annotations


async def test_ocr_rejects_missing_and_invalid_sources(bot_client, fresh_user_dir):
    assert (await bot_client.post("/comfyart/ocr", json={})).status == 400
    assert (await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=nope.png&type=output"})).status == 404
    assert (await bot_client.post("/comfyart/ocr", json={"src": "/api/view?filename=../../x.png&type=output"})).status == 404


def test_parse_lines_real_paddle_ocr_output():
    import json
    from pathlib import Path

    from ComfyArt.api.ocr import clean_text, parse_lines

    data = json.loads((Path(__file__).parent / "fixtures" / "paddle_ocr_smoke.json").read_text())
    lines = parse_lines(data)
    assert [l["text"] for l in lines] == ["COMFYART CLOUD", "Smoke Test 2026"]
    assert lines[0]["box"] == [[60, 456], [966, 456], [966, 571], [60, 571]]
    assert lines[0]["score"] == 0.592 and lines[1]["score"] == 0.677
    # score falls back to layout order, then 1.0
    data["layout_det_res"]["boxes"][0]["coordinate"] = [0, 0, 1, 1]
    data["layout_det_res"]["boxes"].pop()
    assert [l["score"] for l in parse_lines(data)] == [0.592, 1.0]
    assert clean_text("## **Title**\n- item\n1. step") == "Title\n- item\n1. step"


def test_parse_lines_keeps_list_numbering():
    from ComfyArt.api.ocr import parse_lines

    data = {"parsing_res_list": [
        {"block_content": "# Agenda", "block_bbox": [0, 0, 10, 10]},
        {"block_content": "1. Intro", "block_bbox": [0, 20, 10, 30]},
        {"block_content": "2) Plan #2", "block_bbox": [0, 40, 10, 50]},
    ]}
    assert [l["text"] for l in parse_lines(data)] == ["Agenda", "1. Intro", "2) Plan #2"]
