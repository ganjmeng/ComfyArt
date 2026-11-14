"""Paid-generation guard shared by every agent provider (#142).

Every provider (Local LLM, Claude Code, Codex, Qwen Code, DeepSeek...) reaches
the paid tools through the same MCP endpoint (``/comfyart/mcp?bot_chat=...``),
whose handlers relay the run to WaveSpeed. ``api/mcp.py`` asks this module
before a paid tool runs, so the rules hold for all of them:

* per turn, each update_plan item gets at most 4 paid images, or exactly N
  when the user named a count, or the quoted plan's paid units when the user
  named no whole-group count (#909); declined, cancelled and failed runs don't
  count. Past the cap nothing is submitted, the turn is stopped and ends with
  the localized stop notice (same red notice and language plumbing as #137);
* after the user declines a cost confirm on a plan item, further paid calls for
  that same item are refused without opening another dialog (#127); the tool
  result tells the agent to reply as normal chat text (not the #137 red stop);
* in a product task where the user supplied an image, generate_image /
  generate_video calls that don't pass it are refused before submitting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..bot.guide import PAID_TOOLS
from ..bot.external_context import clip_image_blocks
from ..bot.local_llm import (
    _MAX_STEPS_ENV,
    _SKILL_HINT_RE,
    _reply_lang,
    _step_label,
    _step_limit_summary,
    max_steps_from,
)

_log = logging.getLogger(__name__)

DEFAULT_CAP = 4
CAP_TEXT = {
    "zh": "已生成 {n} 张仍未完成，已停止，未继续扣费，请告诉我怎么调整",
    "en": "Generated {n} images and still not done, so I stopped; no further "
          "charges. Tell me how to adjust.",
}
# #127: user cancelled the cost confirm — normal reply, not the #137 red stop.
DECLINED_TEXT = {
    "zh": "已取消该生成，未扣费。请用正常回复告诉用户，并询问如何调整；"
          "本轮不要再提交这一项。",
    "en": "Cancelled this generation; nothing was charged. Tell the user in a "
          "normal reply and ask how to adjust; do not resubmit this plan item "
          "in this turn.",
}
REF_BLOCK_TEXT = (
    "blocked before submitting (nothing was charged): the user supplied the "
    "product image {ids}. Every {tool} call must pass it - put the shape id in "
    "{field}. Describing it in the prompt does not send the image.")
_ZH_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}
_EN_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_COUNT_RE = re.compile(
    r"(\d+|\b(?:" + "|".join(_EN_NUM) + r")\b|[一两二三四五六七八九十])"
    r"\s*(?:张|幅|款|个版本|images?\b|pictures?\b|photos?\b|versions?\b"
    r"|variations?\b)", re.I)
# #909: a count attached (within its clause) to one concrete item of the set
# describes that item, not the whole group's total.
_ITEM_AFTER_RE = re.compile(
    r"(?:主图|副图|场景图|模特图|上身图|细节图|白底图|首图|轮播图|详情图|"
    r"正面图|侧面图|背面图|平铺图|场景|模特|上身|细节|"
    r"\bhero\s+(?:image|shot|photo|visual)\b|"
    r"\bmain\s+(?:image|shot|photo|visual)\b|"
    r"\bprimary\s+(?:image|shot|photo)\b|"
    r"\bcover\s+(?:image|shot|photo)\b|"
    r"\bscene\s+(?:image|shot|photo)\b|"
    r"\blifestyle\s+(?:image|shot|photo)\b|"
    r"\bmodel\s+(?:image|shot|photo)\b|"
    r"\bdetail\s+(?:image|shot|photo)\b)", re.I)
# "主图一张" / "场景图两张": the item comes before its count.
_ITEM_BEFORE_RE = re.compile(
    r"(?:主图|副图|场景图|模特图|上身图|细节图|白底图|首图|轮播图|详情图|"
    r"正面图|侧面图|背面图|平铺图|场景|模特|上身|细节)"
    r"\s*(?:要|做|出|来|是|有)?\s*$", re.I)
# English item counts carry a word between the number and the measure
# ("2 scene shots"), so _COUNT_RE alone does not see them.
_EN_ITEM_COUNT_RE = re.compile(
    r"\b(\d+|\b(?:" + "|".join(_EN_NUM) + r")\b)\s+"
    r"(?:main|hero|primary|cover|scene|lifestyle|model|detail|product)\s+"
    r"(?:images?|shots?|photos?|visuals?)\b", re.I)
# "两张图" / "3 images": a generic count names the set itself, not one item.
_GENERIC_AFTER_RE = re.compile(r"^\s*(?:图|图片|照片|画面|海报|插画|作品|设计)", re.I)
_EN_MEASURE_RE = re.compile(
    r"(?:images?|pictures?|photos?|versions?|variations?)\s*$", re.I)
# "一张主图，几张场景图": a vague part still makes the message an enumeration.
_VAGUE = r"(?:几|若干|数|一些)"
_ITEM_ZH = (r"主图|副图|场景图|模特图|上身图|细节图|白底图|首图|轮播图|详情图|"
            r"正面图|侧面图|背面图|平铺图|场景|模特|上身|细节")
_VAGUE_ITEM_RE = re.compile(
    _VAGUE + r"\s*(?:张|幅|款)\s*(?:" + _ITEM_ZH + r")|"
    r"(?:" + _ITEM_ZH + r")\s*" + _VAGUE + r"\s*(?:张|幅|款)", re.I)
_EN_VAGUE_ITEM_RE = re.compile(
    r"\b(?:a few|several|some|a couple of)\s+"
    r"(?:main|hero|primary|cover|scene|lifestyle|model|detail|product)\s+"
    r"(?:images?|shots?|photos?|visuals?)\b", re.I)
# #909: "…，再加几张…" describes parts of a group; without an explicit total it
# must not turn the first part into a whole-turn cap.
_COMPOSITION_RE = re.compile(
    r"(?:再做|再要|再补|再加|再加上|再出|再生成|再画|再拍|另做|另外|还有|"
    r"以及|分别|外加|另加|\+|\bplus\b|\bas well as\b|\balong with\b|"
    r"\band also\b|\bseparately\b|\bin addition\b|\band a few\b|"
    r"\band several\b|\band some\b)", re.I)
# A number right after one of these is the entire group's total even when the
# message also lists its parts ("一共 4 张：一张主图，再加两张场景图").
_TOTAL_BEFORE_RE = re.compile(
    r"(?:(?:一共|总共|共计|合计|总计|整组|整套|全套|一组|一套|加起来|共有|共)"
    r"\s*(?:要|做|出|生成|画|拍|给我|来|是|有)?|"
    r"\b(?:a\s+total\s+of|total\s+of|in\s+total|a\s+set\s+of|a\s+series\s+of|"
    r"set\s+of|series\s+of|altogether|overall|total)\b)\s*$", re.I)
_TOTAL_AFTER_RE = re.compile(
    r"^\s*(?:in\s+total|total\b|altogether\b|一共|总共|合计|共)", re.I)
# "做 3 张" / "就要 1 张": a making/asking verb turns a bare count into the
# whole-group total, so it wins over a later item list.
_VERB_BEFORE_RE = re.compile(
    r"(?:帮我|给我|就要|只做|只要|只出|只画|需要|想要|想做|做|要|来|出|画|"
    r"生成|拍|设计|制作|输出|make|generate|create|produce|draw|paint|render|"
    r"give|need|want)\s*$", re.I)
_ORDINAL_BEFORE_RE = re.compile(r"(?:第|the)\s*$", re.I)
_CLAUSE_END_RE = re.compile(
    r"[，。；、：！？,;:.!?\n]|再加|另外|还有|以及|分别|\bplus\b", re.I)
_SHAPE_ID_RE = re.compile(r"shape:[A-Za-z0-9_\-]+")
_PRODUCT_RE = re.compile(r"产品|商品|电商|\bproducts?\b", re.I)
REF_FIELDS = {
    "generate_image": ("refs", "base"),
    "generate_video": ("first_frame", "last_frame", "reference_images"),
}


def _count_value(raw: str) -> int:
    raw = (raw or "").strip()
    if raw.isdigit():
        return int(raw)
    return _ZH_NUM.get(raw) or _EN_NUM.get(raw.lower(), 0)


def requested_count(user_text: str) -> int:
    """The whole group's image count ("做 6 张", "3 images"), else 0.

    #909: only an explicit whole-group total sets the paid-guard cap. A count
    that belongs to one item of a list ("一张主图，两张场景图") must not become
    the total; a lone item request ("做一张主图") still counts as 1. Vague
    amounts (几张 / a few) never become a number.
    """
    text = _SKILL_HINT_RE.sub("", user_text or "")
    totals: list[int] = []
    generics: list[int] = []
    plain: list[int] = []
    items: list[int] = []
    for m in _COUNT_RE.finditer(text):
        n = _count_value(m.group(1))
        if not n:
            continue
        before = text[max(0, m.start() - 16):m.start()]
        after = text[m.end():m.end() + 16]
        if _TOTAL_BEFORE_RE.search(before) or _TOTAL_AFTER_RE.search(after):
            totals.append(n)
            continue
        if _ORDINAL_BEFORE_RE.search(before):
            continue  # 第二张图 / the 2 images name one of them, not a new total
        clause = _CLAUSE_END_RE.split(after, 1)[0]
        if _ITEM_AFTER_RE.search(clause) or _ITEM_BEFORE_RE.search(before):
            items.append(n)
        elif _VERB_BEFORE_RE.search(before):
            totals.append(n)  # "做 3 张": an explicit whole-group total
        elif _GENERIC_AFTER_RE.search(clause) or _EN_MEASURE_RE.search(m.group(0)):
            generics.append(n)
        else:
            plain.append(n)
    for m in _EN_ITEM_COUNT_RE.finditer(text):
        n = _count_value(m.group(1))
        if n:
            items.append(n)
    vague_item = bool(_VAGUE_ITEM_RE.search(text) or _EN_VAGUE_ITEM_RE.search(text))
    if totals:
        return max(totals)
    if _COMPOSITION_RE.search(text):
        return 0  # "…，再加…" / "… plus …": parts of a set, no stated total
    if generics:
        total = max(generics)
        # "两张图，一张主图一张场景" states 2; parts that already exceed it do not.
        if items and sum(items) > total:
            return 0
        return total
    if plain:
        return max(plain)
    if len(items) >= 2 or (items and vague_item):
        return 0  # several parallel items, no whole-group total
    if items:
        return items[0]  # one item only: "做一张主图" is still 1
    return 0


def product_refs(provider_text: str) -> list[str]:
    """Image shape ids the user supplied for a product task.

    Attached images arrive as "[Attached image 1: shape id shape:x ...]"; users
    can also name an id in the text. Audio/video attachments don't count."""
    text = provider_text or ""
    skill = re.search(r"Use the ComfyArt skill '([^']+)'", text)
    body = _SKILL_HINT_RE.sub("", text)
    if not ((skill and skill.group(1) == "product") or _PRODUCT_RE.search(body)):
        return []
    ids: list[str] = []
    for line in body.splitlines():
        if re.match(r"\s*\[Attached (audio|video)", line):
            continue
        for sid in _SHAPE_ID_RE.findall(line):
            if sid not in ids:
                ids.append(sid)
    return ids


def passes_ref(name: str, args: dict, refs: list[str]) -> bool:
    fields = REF_FIELDS.get(name)
    if not fields or not refs:
        return True
    given: list[str] = []
    for f in fields:
        v = args.get(f)
        given += [str(x) for x in v] if isinstance(v, list) else [str(v or "")]
    return any(r in given for r in refs)


def gen_units(name: str, args: dict) -> int:
    if name == "generate_image":
        try:
            return max(1, int(args.get("count") or 1))
        except (TypeError, ValueError):
            return 1
    return 1


def active_plan_item(args: dict) -> Optional[str]:
    steps = args.get("steps")
    if not isinstance(steps, list):
        return None
    for st in steps:
        if isinstance(st, dict) and st.get("status") == "active":
            return str(st.get("text") or "")
    return ""


def charged(payload: Any) -> bool:
    """A declined, cancelled or failed run charged nothing."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return True
    return not (isinstance(payload, dict) and (
        payload.get("cancelled") or payload.get("error")
        or payload.get("status") in ("declined", "cancelled", "failed")))


def user_declined(payload: Any) -> bool:
    """True when the user cancelled the cost confirm (not a failed run)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return False
    return isinstance(payload, dict) and (
        bool(payload.get("cancelled"))
        or payload.get("status") in ("declined", "cancelled"))


@dataclass
class TurnGuard:
    lang: str
    cap: int
    refs: list[str]
    on_stop: Optional[Callable[[], None]] = None
    plan_item: str = ""
    used: dict[str, int] = field(default_factory=dict)
    done: list[str] = field(default_factory=list)
    stopped: str = ""
    declined_items: set[str] = field(default_factory=set)
    # #238: external CLIs only. The built-in agent counts steps in its own loop.
    external_steps: int = 0
    screenshots_sent: int = 0
    # User's own words for ask-card language (same rule as ask_card_lang).
    goal_text: str = ""
    # #909: the explicit group total from the user, 0 when they named none.
    # The plan quote may raise the cap only in that second case.
    user_count: int = 0

    def summary(self) -> str:
        counts: dict[str, int] = {}
        for label in self.done:
            counts[label] = counts.get(label, 0) + 1
        items = [k + (f" ×{c}" if c > 1 else "") for k, c in counts.items()]
        if self.lang == "zh":
            return (CAP_TEXT["zh"].format(n=self.cap) + "。已完成："
                    + ("、".join(items) if items else "无") + "。")
        return (CAP_TEXT["en"].format(n=self.cap) + " Done so far: "
                + (", ".join(items) if items else "nothing") + ".")


TURNS: dict[str, TurnGuard] = {}

NOTURN_PREFIX = "__noturn__:"


class PaidRefused(Exception):
    """Raised by the paid-tool handler wrap when before_call blocks the submit (#730)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def noturn_key(session_or_client: str) -> str:
    tag = (session_or_client or "").strip() or "anonymous"
    return f"{NOTURN_PREFIX}{tag}"


def ensure_noturn(chat_id: str) -> TurnGuard:
    """Open a default-cap guard for a no-turn MCP client; no-op if one already exists."""
    existing = TURNS.get(chat_id)
    if existing is not None:
        return existing
    if not chat_id.startswith(NOTURN_PREFIX):
        raise ValueError(f"ensure_noturn expects a {NOTURN_PREFIX!r} key, got {chat_id!r}")
    return begin_turn(chat_id, text="", provider_text="", lang="en")


def resolve_guard_chat_id() -> str:
    """Chat id for the paid guard: explicit guard key, bot chat, or anonymous noturn."""
    from .mcp_tools._context import BOT_CHAT_ID, GUARD_CHAT_ID
    return GUARD_CHAT_ID.get() or BOT_CHAT_ID.get() or noturn_key("anonymous")



def begin_turn(chat_id: str, *, text: str, provider_text: str, lang: str = "",
               on_stop: Optional[Callable[[], None]] = None) -> TurnGuard:
    """Open the guard for one turn. ``text`` is what the user typed (the count
    comes from it); ``provider_text`` also carries attached-image lines."""
    count = requested_count(text)
    guard = TurnGuard(
        lang=lang if lang in ("zh", "en") else _reply_lang(text),
        cap=count or DEFAULT_CAP,
        refs=product_refs(provider_text),
        on_stop=on_stop,
        goal_text=text,
        user_count=count)
    TURNS[chat_id] = guard
    return guard


def allow_planned_cap(chat_id: str, units: int) -> None:
    """#909: when the user stated no group total, the confirmed plan sets the cap.

    The quote card has already shown this many paid units and the user started it
    (or it was under the confirm line); a text-derived DEFAULT_CAP must not block
    a plan of 5+ images. An explicit user count is never raised: "做 3 张" still
    means exactly 3 (AC1).
    """
    guard = TURNS.get(chat_id)
    if guard is None or guard.user_count:
        return
    try:
        n = int(units)
    except (TypeError, ValueError):
        return
    if n > guard.cap:
        guard.cap = n


def end_turn(chat_id: str) -> str:
    """Close the turn; returns the stop notice if the cap stopped it."""
    guard = TURNS.pop(chat_id, None)
    return guard.stopped if guard else ""


def external_step_limit() -> int:
    """#238: same cap as the built-in agent (setting, or COMFYART_AGENT_MAX_STEPS)."""
    import os

    from .settings import get_setting

    env = os.environ.get(_MAX_STEPS_ENV)
    if env:
        return max_steps_from(env)
    return max_steps_from(get_setting("bot-max-steps"))


def _external_step_block(guard: TurnGuard) -> Optional[str]:
    """Refuse the call once this external turn has used its step budget. Nothing runs."""
    if guard.stopped:
        return guard.stopped
    limit = external_step_limit()
    if guard.external_steps >= limit:
        guard.stopped = _step_limit_summary(guard.done, limit, guard.lang)
        if guard.on_stop:
            guard.on_stop()
        return guard.stopped
    guard.external_steps += 1
    return None


def fallback_allowed(chat_id: str, name: str, args: dict) -> bool:
    """#236: a fallback submit has to stay inside this turn's cost rules.

    Read-only. A missing guard allows it (the MCP check still runs on the real
    call). Over the cap, a declined plan item, a stopped turn, or a missing
    product reference all refuse it, and nothing here stops the turn or submits.
    """
    guard = TURNS.get(chat_id)
    if guard is None or name not in PAID_TOOLS:
        return True
    if guard.stopped or guard.plan_item in guard.declined_items:
        return False
    if not passes_ref(name, args, guard.refs):
        return False
    used = guard.used.get(guard.plan_item, 0)
    return used + gen_units(name, args) <= guard.cap


def before_call(chat_id: str, name: str, args: dict, *, external: bool = False) -> Optional[str]:
    """None to let the call run; otherwise the error text (nothing submitted)."""
    guard = TURNS.get(chat_id)
    if guard is None and chat_id.startswith(NOTURN_PREFIX):
        guard = ensure_noturn(chat_id)
    if guard is None:
        return None
    if external:
        # A stopped external turn refuses every later tool, paid or not.
        blocked = _external_step_block(guard)
        if blocked:
            return blocked
    if name not in PAID_TOOLS:
        return None
    if guard.stopped:
        return guard.stopped
    if guard.plan_item in guard.declined_items:
        return DECLINED_TEXT.get(guard.lang, DECLINED_TEXT["en"])
    if not passes_ref(name, args, guard.refs):
        return REF_BLOCK_TEXT.format(ids=", ".join(guard.refs), tool=name,
                                     field=REF_FIELDS[name][0])
    used = guard.used.get(guard.plan_item, 0)
    if used + gen_units(name, args) > guard.cap:
        _log.warning("[ComfyArt/paid-guard] chat %s: %s on plan item %r used "
                     "%d of %d, stopping", chat_id, name, guard.plan_item,
                     used, guard.cap)
        guard.stopped = guard.summary()
        if guard.on_stop:
            guard.on_stop()
        return guard.stopped
    return None


def after_call(chat_id: str, name: str, args: dict, payload: Any,
               ok: bool) -> None:
    guard = TURNS.get(chat_id)
    if guard is None:
        return
    if ok:
        guard.done.append(_step_label(name, args, guard.lang))
    if not ok:
        return
    if name == "update_plan":
        item = active_plan_item(args)
        if item is not None:
            guard.plan_item = item
    elif name in PAID_TOOLS:
        if charged(payload):
            guard.used[guard.plan_item] = (guard.used.get(guard.plan_item, 0)
                                           + gen_units(name, args))
        elif user_declined(payload):
            # At most one cost-confirm dialog per plan item this turn (#127).
            guard.declined_items.add(guard.plan_item)


def clip_external_screenshots(chat_id: str, blocks: list[dict]) -> list[dict]:
    """#238: at most 2 screenshot images returned to an external CLI during one bot turn.

    #730 no-turn buckets (``__noturn__:``) cap paid submits. They are not a bot turn, so
    this cap stays off and a direct MCP call still returns every image (#804).
    """
    if not chat_id or chat_id.startswith(NOTURN_PREFIX):
        return blocks
    guard = TURNS.get(chat_id)
    if guard is None or not blocks:
        return blocks
    clipped, guard.screenshots_sent = clip_image_blocks(
        blocks, already_sent=guard.screenshots_sent)
    return clipped


def stop_later(provider: Any, handle: Any) -> Callable[[], None]:
    """on_stop for a live turn: flag it now, stop the provider once the
    refused call's response is on its way."""
    def _stop() -> None:
        handle.stop_requested = True
        loop = asyncio.get_running_loop()
        loop.call_later(0.2, lambda: asyncio.ensure_future(provider.stop(handle)))
    return _stop
