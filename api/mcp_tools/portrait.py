"""portrait-studio replies and single-image redo (Lovart 7fc60c86 reply, review-assets notes.txt).

portrait_studio_plan   before generating: records the set (card answers + what the agent read off the
                       reference) and returns reply (1) — locked / changed, lighting, optics, pose,
                       「现在开始生成」 — for the agent to post once, verbatim.
generate_image         with skill portrait-studio and portrait_slot N: one image for slot N; the server
                       writes that slot's shot size, outfit, scene, light, lens and pose into the prompt.
portrait_studio_done   after wait_generation: records the placed image per slot and returns replies (2)
                       table + parameters and (3) the closing check, verbatim, once.
portrait_studio_redo   the user names ONE image (「半身那张脸不像」 / "redo #2"): exactly one
                       generate_image (same reference, same shot, same outfit/scene, count 1), placed
                       next to the original. The original and the other images are not touched.
None of these tools call a model themselves; redo goes through the normal generate_image handler
(run approval, pin, quote for that one image).
"""
from __future__ import annotations

from .. import portrait_studio as ps
from ._context import BOT_CHAT_ID


def _chat() -> str:
    return str(BOT_CHAT_ID.get() or "")


def _failed(error: str) -> dict:
    return {"status": "failed", "submitted": False, "charged": False, "error": error, "kind": "portraitStudioArgs"}


async def portrait_studio_plan(args: dict) -> dict:
    try:
        plan = ps.make_plan(args)
    except ps.PlanError as e:
        return _failed(str(e))
    ps.PLANS[_chat()] = plan
    return {
        "status": "planned", "submitted": False, "charged": False, "lang": plan["lang"],
        "user_message": ps.plan_text(plan),
        "slots": [{"slot": i, "shot": s} for i, s in enumerate(plan["shots"], 1)],
        "note": ("Post user_message verbatim, once, as your reply before generating. Then call generate_image once "
                 "per slot with skill \"portrait-studio\", the same refs, count 1 and portrait_slot set to the slot "
                 "number; wait_generation; then call portrait_studio_done with the placed image ids in slot order."),
    }


async def portrait_studio_done(args: dict) -> dict:
    plan = ps.PLANS.get(_chat())
    if not plan:
        return _failed("no portrait-studio set in this chat: call portrait_studio_plan first")
    images = [str(i) for i in (args.get("images") or []) if str(i).strip()]
    if len(images) != len(plan["shots"]):
        return _failed(f"images must list {len(plan['shots'])} placed image ids in slot order, got {len(images)}")
    plan["images"] = {i: sid for i, sid in enumerate(images, 1)}
    return {
        "status": "done", "charged": False, "lang": plan["lang"],
        "user_message": ps.done_text(plan) + "\n\n" + ps.closing_text(plan),
        "note": "Post user_message verbatim, once, as your final reply. Do not add other parameters.",
    }


async def portrait_studio_redo(args: dict) -> dict:
    plan = ps.PLANS.get(_chat())
    if not plan:
        return _failed("no portrait-studio set in this chat to redo: run the portrait-studio flow first")
    try:
        slot = ps.resolve_slot(plan, args.get("slot"), args.get("shot"))
    except ps.PlanError as e:
        return _failed(str(e))
    from .canvas import TOOLS
    gen = ps.redo_args(plan, slot, str(args.get("fix") or ""))
    gen["portrait_slot"] = slot
    result = await TOOLS["generate_image"]["handler"](gen)
    if isinstance(result, dict) and result.get("ids"):
        plan["redos"].append({"slot": slot, "near": plan["images"].get(slot), "ids": result.get("ids")})
    lang = plan["lang"]
    shot = ps.SHOTS[plan["shots"][slot - 1]][lang]
    out = dict(result) if isinstance(result, dict) else {"result": result}
    out.update(portrait_slot=slot, shot=plan["shots"][slot - 1], near=plan["images"].get(slot),
               user_message=ps.REDO_TEXT[lang].format(i=slot, shot=shot if lang == "zh" else shot.lower()),
               note=("Exactly one image is being redone. Post user_message, call wait_generation with these ids, and "
                     "do not regenerate or delete any other image. Do not call portrait_studio_done again."))
    return out


_STR = {"type": "string"}
TOOLS: dict[str, dict] = {
    "portrait_studio_plan": {
        "description": (
            "portrait-studio only, after the card is answered and BEFORE any generate_image. Records the set and "
            "returns user_message: the reply to post once, verbatim (what stays locked from the reference, what "
            "changes, lighting, lens, pose, then that generation starts). shots / outfit / scene: the card answer "
            "ids (A/B/C) or the user's own words. locked: what you see in the reference photo that stays (face "
            "features, hair, skin tone, build), short items in the reply language. outfit_desc: the reference "
            "outfit in a few words (used when the outfit is kept). reference_background: the reference photo's "
            "background in a few words. prompt: an English description of the person for every image."),
        "inputSchema": {"type": "object", "properties": {
            "refs": {"type": "array", "items": _STR}, "shots": _STR, "outfit": _STR, "scene": _STR,
            "locked": {"type": "array", "items": _STR}, "outfit_desc": _STR, "reference_background": _STR,
            "prompt": _STR}, "required": ["refs", "locked"], "additionalProperties": False},
        "handler": portrait_studio_plan,
    },
    "portrait_studio_done": {
        "description": (
            "portrait-studio only, after wait_generation placed every slot. images: the placed image shape ids in "
            "slot order. Returns user_message: the shot-size table, the parameters used and the closing check, "
            "to post once, verbatim, as the final reply."),
        "inputSchema": {"type": "object", "properties": {"images": {"type": "array", "items": _STR}},
                        "required": ["images"], "additionalProperties": False},
        "handler": portrait_studio_done,
    },
    "portrait_studio_redo": {
        "description": (
            "portrait-studio only: the user says ONE image of the set is off (e.g. 「半身那张脸不像」, 「重做第2张」, "
            "\"redo #2\"). Starts exactly one generate_image for that image (same reference, shot size, outfit and "
            "background), placed next to the original; the original and the other images stay. slot: the image "
            "number (1-based) or shot: its shot size as the user said it. fix: optional English note on what to "
            "correct. Returns ids for wait_generation. Never call generate_image yourself for a redo, and never "
            "redo more than the one image the user named."),
        "inputSchema": {"type": "object", "properties": {"slot": {"type": "integer"}, "shot": _STR, "fix": _STR},
                        "additionalProperties": False},
        "handler": portrait_studio_redo,
    },
}
