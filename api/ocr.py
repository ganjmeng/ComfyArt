import json
import re

from aiohttp import web

from . import wavespeed
from ._common import error, json_body, routes, view_path

# OCR runs on WaveSpeed (wavespeed-ai/paddle-ocr) instead of the local RapidOCR model.


def _box(value) -> list[list[int]] | None:
    if not isinstance(value, list) or not value:
        return None
    if all(isinstance(v, (int, float)) for v in value):
        if len(value) == 4:
            x1, y1, x2, y2 = (round(float(v)) for v in value)
            return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        if len(value) == 8:
            return [[round(float(value[i])), round(float(value[i + 1]))] for i in range(0, 8, 2)]
        return None
    if len(value) == 4 and all(isinstance(p, list) and len(p) == 2 for p in value):
        return [[round(float(x)), round(float(y))] for x, y in value]
    return None


MARKDOWN = re.compile(r"^\s*#{1,6}\s+")  # heading markers only; list numbering like "1." is real text
EMPHASIS = re.compile(r"(\*\*|__|\*|`)")


def clean_text(text: str) -> str:
    """Drop markdown markup PaddleOCR adds to block_content (heading markers, emphasis)."""
    lines = [EMPHASIS.sub("", MARKDOWN.sub("", ln)).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _layout_scores(data: dict) -> tuple[dict, dict]:
    by_box: dict = {}
    by_order: dict = {}
    for b in ((data.get("layout_det_res") or {}).get("boxes") or []):
        if not isinstance(b, dict) or not isinstance(b.get("score"), (int, float)):
            continue
        if isinstance(b.get("coordinate"), list):
            by_box[tuple(round(float(v)) for v in b["coordinate"][:4])] = b["score"]
        if b.get("order") is not None:
            by_order[b["order"]] = b["score"]
    return by_box, by_order


def parse_lines(data) -> list[dict]:
    """Collect {text, box, score} entries from PaddleOCR JSON, whatever nesting it uses."""
    lines: list[dict] = []
    scores: tuple[dict, dict] = ({}, {})

    def walk(node):
        nonlocal scores
        if isinstance(node, dict):
            if "layout_det_res" in node:
                scores = _layout_scores(node)
            text = next((node[k] for k in ("text", "content", "rec_text", "block_content") if isinstance(node.get(k), str)), None)
            raw_box = next((node.get(k) for k in ("box", "bbox", "poly", "points", "block_bbox", "coordinate") if _box(node.get(k))), None)
            box = _box(raw_box) if raw_box is not None else None
            text = clean_text(text) if text else ""
            if text and box:
                score = node.get("score") or node.get("confidence") or node.get("rec_score")
                if not isinstance(score, (int, float)) and isinstance(raw_box, list) and len(raw_box) == 4 and all(isinstance(v, (int, float)) for v in raw_box):
                    score = scores[0].get(tuple(round(float(v)) for v in raw_box))
                if not isinstance(score, (int, float)) and node.get("block_order") is not None:
                    score = scores[1].get(node["block_order"])
                lines.append({"box": box, "text": text, "score": round(float(score), 3) if isinstance(score, (int, float)) else 1.0})
                return
            for k, v in node.items():
                if k != "layout_det_res":  # layout boxes carry no text, only scores
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return lines


async def read_lines(url: str) -> list[dict]:
    view_path(url)  # validates the URL points at an existing ComfyUI file
    outputs = await wavespeed.run_raw({"feature": "ocr", "image": url, "params": {"output_format": "json"}})
    lines: list[dict] = []
    for out in outputs:
        text = out if not isinstance(out, str) or not out.startswith(("http://", "https://")) else await wavespeed.fetch_text(out)
        try:
            data = json.loads(text) if isinstance(text, str) else text
        except ValueError:
            continue
        lines.extend(parse_lines(data))
    return lines


@routes.post("/comfyart/ocr")
async def ocr(request: web.Request) -> web.Response:
    body = await json_body(request)
    url = body.get("src")
    if not isinstance(url, str) or not url:
        return error("src must be a /api/view URL", 400)
    try:
        lines = await read_lines(url)
    except (ValueError, OSError) as e:
        return error(str(e), 404)
    except wavespeed.WaveSpeedError as e:
        return error(str(e), e.status)
    return web.json_response({"lines": lines})
