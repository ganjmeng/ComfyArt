"""#707: linkedin-banner is 1584×396. Passing width and height is not enough when the
model schema snaps them to an aspect ratio.

A model can take that canvas only when the adapter would submit size ``W*H`` and
would not also send a snapped aspect_ratio. That is read from the catalog schema.
``wavespeed-ai/qwen-image-2.0/text-to-image`` is preferred only when its schema
says so; it is not treated as capable if the field is missing. An aspect enum
that merely contains ``4:1`` is not an exact pixel size.

No WaveSpeed call lives here.
"""
from __future__ import annotations

from .wavespeed import _nearest, _resolution, _schema, _size_value

SKILL = "linkedin-banner"
# Skills whose auto path must submit exact pixels. Others stay on the normal table.
EXACT_SKILLS = frozenset({SKILL, "before-after"})
# Used only after accepts_exact_pixels is true and the id is on the curated feature list.
VERIFIED = {
    "text_to_image": "wavespeed-ai/qwen-image-2.0/text-to-image",
    "image_edit": "wavespeed-ai/qwen-image-2.0/edit",
}


def running_feature(args: dict) -> str:
    if args.get("refs") or args.get("base"):
        return "image_edit"
    return "text_to_image"


def pixels_of(args: dict) -> tuple[int, int] | None:
    try:
        w, h = int(args.get("width")), int(args.get("height"))
    except (TypeError, ValueError):
        return None
    if w < 1 or h < 1:
        return None
    return w, h


def provider_submit(schema: dict, w: int, h: int) -> dict:
    """The size fields build_payload would send. No HTTP."""
    props = (schema or {}).get("properties") or {}
    out: dict = {}
    if "size" in props and not (props.get("size") or {}).get("x-hidden"):
        out["size"] = _size_value(props["size"], int(w), int(h))
    enum = (props.get("aspect_ratio") or {}).get("enum")
    if enum:
        out["aspect_ratio"] = _nearest(list(enum), int(w) / int(h))
    res = (props.get("resolution") or {}).get("enum")
    if res:
        out["resolution"] = _resolution(list(res), max(int(w), int(h)))
    return out


def accepts_exact_pixels(schema: dict, w: int, h: int) -> bool:
    """True only when the submit is the exact ``W*H`` string and no snapped ratio."""
    sent = provider_submit(schema, w, h)
    return sent.get("size") == f"{int(w)}*{int(h)}" and "aspect_ratio" not in sent


def reconcile(requested: tuple[int, int], provider_pixels: tuple[int, int] | None) -> dict:
    """Compare a locked canvas with pixels read from the provider file.

    ``provider_pixels`` is None when the file could not be decoded. Delivery is
    those file pixels only when they match; this does not resize anything.
    """
    req = {"width": int(requested[0]), "height": int(requested[1])}
    if provider_pixels is None:
        return {"requested": req, "provider_output": None, "delivered": None, "match": False}
    got = {"width": int(provider_pixels[0]), "height": int(provider_pixels[1])}
    return {"requested": req, "provider_output": got, "delivered": dict(got), "match": got == req}


def file_pixels(data: bytes) -> tuple[int, int] | None:
    """Pixel size of a downloaded provider file, or None when the bytes are not an image."""
    import io

    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
        if int(w) < 1 or int(h) < 1:
            return None
        return int(w), int(h)
    except Exception:  # noqa: BLE001 - unreadable bytes are a failed size check, not a delivery
        return None


def size_reject(requested: tuple[int, int], provider: tuple[int, int] | None) -> str:
    """Explicit completion failure. The prefix is kept by the UI error allowlist."""
    w, h = int(requested[0]), int(requested[1])
    if provider is None:
        return (f"没有通过：供应商原文件读不出像素，不能当成 {w}×{h} 交付。没有拉伸，没有裁切，没有重试，没有换模型。"
                f" / Not accepted: the provider file has no readable pixels, so it was not delivered as {w}×{h}. "
                "It was not stretched, cropped, retried, or sent to another model.")
    gw, gh = int(provider[0]), int(provider[1])
    return (f"没有通过：供应商原文件是 {gw}×{gh}，锁定尺寸是 {w}×{h}。没有拉伸，没有裁切，没有重试，没有换模型。"
            f" / Not accepted: the provider file is {gw}×{gh} and the locked size is {w}×{h}. "
            "It was not stretched, cropped, retried, or sent to another model.")


def audit_file(data: bytes, requested: tuple[int, int]) -> dict:
    """Read one provider file and reconcile it with the locked size. No network, no resize."""
    got = file_pixels(data)
    out = reconcile(requested, got)
    out["read_error"] = got is None
    out["error"] = None if out["match"] else size_reject(requested, got)
    return out


def _block(model: str, w: int, h: int, submit: dict, *, why: str) -> dict:
    return {
        "status": "failed",
        "submitted": False,
        "generation_succeeded": False,
        "model": model,
        "requested_size": {"width": w, "height": h},
        "provider_submit": submit,
        "provider_output": None,
        "delivered_size": None,
        "error": why,
        "note": why,
    }


def _snap_sentence(submit: dict) -> str:
    if not submit.get("aspect_ratio") and not submit.get("size"):
        return "它的接口没有可提交的自定义宽高。"
    if submit.get("size") and submit.get("size") != "":
        extra = f"，并带上比例 {submit['aspect_ratio']}" if submit.get("aspect_ratio") else ""
        return f"它会提交 size={submit['size']}{extra}，不是只按请求像素。"
    bits = []
    if submit.get("aspect_ratio"):
        bits.append(f"比例 {submit['aspect_ratio']}")
    if submit.get("resolution"):
        bits.append(f"分辨率 {submit['resolution']}")
    return "它只会改成" + "、".join(bits) + "，不是目标像素。"


def linkedin_fallback_block(args: dict, failed: str) -> dict:
    """A failed linkedin-banner call is not retried on a model that would snap the canvas."""
    wh = pixels_of(args) or (1584, 396)
    why = (f"没有提交：{failed} 失败后，没有改用不能输出 {wh[0]}×{wh[1]} 的模型，也没有拉伸。"
           f" / Not submitted: after {failed} failed, no model that cannot output {wh[0]}×{wh[1]} was substituted.")
    return _block(str(failed), wh[0], wh[1], {}, why=why)


def linkedin_decision(args: dict, catalog: dict, _cfg: dict) -> dict:
    """Auto keeps a schema-exact model. A named incompatible model is refused before submit."""
    wh = pixels_of(args)
    skill = str(args.get("skill") or SKILL)
    if wh is None:
        why = (f"没有提交：{skill} 没有可用的宽高，没有生成。 / Not submitted: {skill} had no pixel size.")
        return {"block": _block("", 0, 0, {}, why=why)}
    w, h = wh
    feature = running_feature(args)
    named = str(args.get("model") or "")
    if named:
        schema = _schema((catalog or {}).get(named))
        submit = provider_submit(schema, w, h) if schema else {}
        if not accepts_exact_pixels(schema, w, h):
            detail = _snap_sentence(submit)
            why = (f"没有提交：{named} 不能输出 {w}×{h}。{detail}没有换模型，也没有拉伸。"
                   f" / Not submitted: {named} cannot output {w}×{h}. No model was substituted and the image was not stretched.")
            return {"block": _block(named, w, h, submit, why=why)}
        kept = {**args, "size_lock": True, "size_candidates": [named]}
        return {"args": kept, "choice": {
            "model": named, "auto": False, "category": "user",
            "reason": {"zh": "你指定了这个模型，并且它的 size 能提交这个宽高",
                       "en": "you named this model, and its size field can submit these pixels"},
            "requested_size": {"width": w, "height": h},
            "provider_submit": submit,
        }}
    prefer = VERIFIED[feature]
    schema = _schema((catalog or {}).get(prefer))
    # Not the Lovart dropdown. The id is used only while this schema makes the adapter
    # submit the exact size string. _cfg is the curated config, unused on purpose:
    # membership there is the picker, not proof of a pixel size. The page still
    # drops the id when the user has turned that model off.
    if not accepts_exact_pixels(schema, w, h):
        why = (f"没有提交：模型列表里没有能按 {w}×{h} 提交 size 的{('图片编辑' if feature == 'image_edit' else '文生图')}模型。"
               f"没有改用只会改比例的模型。 / Not submitted: no listed model can submit size {w}*{h}. "
               "A ratio-only model was not substituted.")
        return {"block": _block("", w, h, {}, why=why)}
    submit = provider_submit(schema, w, h)
    out = {k: v for k, v in args.items() if k not in ("model", "auto_model", "edit_model")}
    out["size_lock"] = True
    out["size_candidates"] = [prefer]
    choice = {
        "model": prefer, "auto": True, "category": "skill_size", "skill": skill,
        "reason": {"zh": f"{skill} 需要 {w}×{h}，{prefer} 的 size 字段能按这个宽高提交",
                   "en": f"{skill} needs {w}×{h}, and {prefer} accepts that exact size"},
        "requested_size": {"width": w, "height": h},
        "provider_submit": submit,
    }
    if feature == "image_edit":
        out["edit_model"] = prefer
        choice["edit_model"] = prefer
    else:
        out["model"] = prefer
    return {"args": out, "choice": choice}
