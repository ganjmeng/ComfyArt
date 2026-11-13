"""#956 / #957: refuse a generate_image call before submit when required skill params are missing.

Applicability is inferred from the current skill and answered cards in this chat,
not from the agent-supplied skill argument alone. When the current portrait
task is still using an uploaded photo, omitting refs, skill, and shot together
is also refused (no silent text-to-image). The guard never injects a shot,
picks a historical image, or overrides an explicit user change; it only
refuses and tells the agent which parameter is missing. Quotes use the same
check and, when the args are complete, the validated parameters that will
actually be submitted.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import chat_store, product_packaging as packaging, portrait_studio as portrait

PORTRAIT = portrait.SKILL
PACKAGING = packaging.SKILL

KIND_MISSING = "missingSkillParams"

_SKILL_START_RE = re.compile(r"Use the ComfyArt skill (['\"])(.+?)\1 for this task")

# The composer sends skill.name (localized), not the skill id. Map both.
_ALIASES: dict[str, str] | None = None


def _aliases() -> dict[str, str]:
    global _ALIASES
    if _ALIASES is not None:
        return _ALIASES
    aliases = {PORTRAIT: PORTRAIT, PACKAGING: PACKAGING}
    root = Path(__file__).resolve().parent.parent
    keys = {"skills.portraitStudio": PORTRAIT, "skills.productToPackaging": PACKAGING}
    for lang in ("zh", "en"):
        path = root / "src" / "locales" / f"{lang}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        for key, sid in keys.items():
            label = str(data.get(key) or "").strip()
            if label:
                aliases[label] = sid
                aliases[label.casefold()] = sid
    _ALIASES = aliases
    return aliases


def canonical_skill(name: str) -> str:
    """portrait-studio / product-to-packaging, or the original string if unrelated."""
    raw = str(name or "").strip()
    if not raw:
        return ""
    aliases = _aliases()
    return aliases.get(raw) or aliases.get(raw.casefold()) or raw


_ERR = {
    "skill": {
        "zh": "generate_image 缺少 skill。请传入 skill='portrait-studio'。未提交，未扣费。",
        "en": "generate_image is missing skill. Pass skill='portrait-studio'. Nothing was submitted or charged.",
    },
    "shot": {
        "zh": "generate_image 缺少当前景别 shot。请传入 shot，且必须是 closeup、half、three_quarter、full 之一。未提交，未扣费。不要猜测景别。",
        "en": "generate_image is missing the current shot. Pass shot as one of: closeup, half, three_quarter, full. Nothing was submitted or charged. Do not guess the shot.",
    },
    "skill_shot": {
        "zh": "generate_image 缺少 skill 或当前景别 shot。请传入 skill='portrait-studio'，以及 shot（closeup / half / three_quarter / full 之一）。未提交，未扣费。不要猜测景别。",
        "en": "generate_image is missing skill or the current shot. Pass skill='portrait-studio' and shot as one of: closeup, half, three_quarter, full. Nothing was submitted or charged. Do not guess the shot.",
    },
    "refs": {
        "zh": "generate_image 缺少 refs。当前 product-to-packaging 任务正在使用上传的产品图，请把该产品图放入 refs。不能改走文生图。未提交，未扣费。不要擅自挑选历史图片。",
        "en": "generate_image is missing refs. This product-to-packaging task is using the uploaded product photo; pass that image in refs. Do not fall back to text-to-image. Nothing was submitted or charged. Do not auto-pick a historical image.",
    },
    "portrait_refs": {
        "zh": "generate_image 缺少 refs。当前人像任务正在使用上传的参考图，请把该参考图放入 refs。不能改走文生图。未提交，未扣费。不要擅自补图或挑选历史图片。",
        "en": "generate_image is missing refs. This portrait-studio task is using the uploaded reference photo; pass that image in refs. Do not fall back to text-to-image. Nothing was submitted or charged. Do not auto-fill or auto-pick a historical image.",
    },
    "skill_shot_refs": {
        "zh": "generate_image 缺少 skill、当前景别 shot，以及 refs。当前人像任务正在使用上传的参考图，请传入 skill='portrait-studio'、shot（closeup / half / three_quarter / full 之一），并把该参考图放入 refs。不能改走文生图。未提交，未扣费。不要猜测景别，不要擅自补图。若用户的任务切换或是否继续用图不明确，请先向用户澄清，不要自行解除保护。",
        "en": "generate_image is missing skill, the current shot, and refs. This portrait-studio task is using the uploaded reference photo; pass skill='portrait-studio', shot as one of: closeup, half, three_quarter, full, and that image in refs. Do not fall back to text-to-image. Nothing was submitted or charged. Do not guess the shot or auto-fill the photo. If task switching or reference use is unclear, ask the user to clarify; do not release the guard yourself.",
    },
}


def _lang() -> str:
    try:
        from . import bot_asks
        got = bot_asks.card_lang()
    except Exception:
        got = ""
    return got if got in ("zh", "en") else "zh"


def _norm_shot(raw: object) -> str:
    return str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")


def _has_ref(args: dict) -> bool:
    refs = (args or {}).get("refs") or []
    if isinstance(refs, str):
        return bool(refs.strip())
    if isinstance(refs, (list, tuple)) and any(str(r).strip() for r in refs):
        return True
    return bool(str((args or {}).get("base") or "").strip())


def _skill_from_block(block: dict) -> str:
    if not isinstance(block, dict):
        return ""
    if block.get("type") == "skill" and block.get("name"):
        return str(block.get("name") or "").strip()
    return ""


def _text_of(block: dict) -> str:
    if not isinstance(block, dict):
        return ""
    return str(block.get("text") or block.get("content") or "")


def _card_kind(block: dict) -> str:
    """portrait / packaging / '' from an ask block or a raw spec."""
    if not isinstance(block, dict):
        return ""
    payload = block
    if block.get("type") == "ask":
        payload = block
    if portrait.is_portrait_card(payload):
        return "portrait"
    if packaging.is_packaging_card(payload):
        return "packaging"
    # answered blocks may only keep question ids in answers
    answers = payload.get("answers")
    if isinstance(answers, dict):
        keys = {str(k) for k in answers}
        if keys & {portrait.PS_SHOTS, portrait.PS_OUTFIT, portrait.PS_SCENE}:
            return "portrait"
        if keys & set(packaging.QUESTION_IDS):
            return "packaging"
    questions = payload.get("questions")
    if isinstance(questions, list):
        ids = {str((q or {}).get("id") or "") for q in questions if isinstance(q, dict)}
        if ids & {portrait.PS_SHOTS, portrait.PS_OUTFIT, portrait.PS_SCENE}:
            return "portrait"
        if ids & set(packaging.QUESTION_IDS):
            return "packaging"
    return ""


def _upload_id(block: dict) -> str:
    if not isinstance(block, dict):
        return ""
    if block.get("type") not in ("image", "file"):
        return ""
    return str(block.get("url") or block.get("src") or block.get("shape") or "").strip()


@dataclass
class GenContext:
    """What this chat's current skill run is, from messages and answered cards."""
    skill: str = ""
    card: str = ""
    answers: dict | None = None
    uploads: list[str] = field(default_factory=list)

    def portrait(self) -> bool:
        if self.skill == PORTRAIT:
            return True
        if self.skill and self.skill != PORTRAIT:
            return False
        return self.card == "portrait"

    def packaging(self) -> bool:
        if self.skill == PACKAGING:
            return True
        if self.skill and self.skill != PACKAGING:
            return False
        return self.card == "packaging"

    def packaging_uses_upload(self) -> bool:
        """True only when this packaging run is explicitly using an uploaded product photo."""
        return self.packaging() and bool(self.uploads)

    def portrait_uses_upload(self) -> bool:
        """True when this portrait run is still using an uploaded reference photo."""
        return self.portrait() and bool(self.uploads)



# Narrow, clause-scoped directives, not a bag of words from the whole message.
# Inconclusive / contradictory language keeps the current upload protection.
_REF_ZH = r"(?:(?:之前|先前|刚才|上传|原来|原|旧|任何|这张|那张|这些)(?:的)?)*(?:参考图|照片|图片|原照|上传照)"
_REF_EN = r"(?:(?:the|any|a|an|previous|old|uploaded|original|reference|portrait|this|that|my|these|her|his|our|their)\s+)*(?:photos?|images?|references?)\b"
_END_ZH = (r"(?:结束|停止|取消)(?:当前|这个|这次|这组|之前的|刚才的)?"
           r"(?:形象照|人像照|人像摄影|人像|肖像)(?:任务|流程|生成)?(?:了|吧)?")
_END_EN = (r"(?:end|stop|cancel)\s+(?:(?:the|this)\s+)?(?:(?:current|previous)\s+)?"
           r"portrait(?:[ -]studio)?(?:\s+(?:task|session|workflow))?")


def _task_directives(text: str) -> set[str]:
    """Recognize affirmative/negative user clauses with local negation scope.

    Never mine directives from quoted examples, subordinate conditions, or
    agent output. All three affirmative facts are needed; a conflicting
    continuation or negated new-task directive vetoes the transition.
    This deliberately does not claim general natural-language understanding.
    """
    text = re.sub(r'```.*?```|`[^`]*`|“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"', '', text, flags=re.S)
    evidence: set[str] = set()
    # Split only clause boundaries, not arbitrary spans inside a directive.
    clauses = re.split(r"[\n，,。；;！!：:]|(?<!\w)\.(?!\w)|(?<=\w)\.(?=\s|$)|\b(?:but|however|and)\b|但(?:是)?|不过|然而|并且|同时", text, flags=re.I)
    for clause in clauses:
        c = re.sub(r"^(?:(?:请|现在|先|我们|也)\s*|please\s+)+", "", clause.strip(), flags=re.I)
        if not c or re.search(r"[？?]", c):
            continue
        ended = bool(re.fullmatch(_END_ZH + "|" + _END_EN, c, re.I))
        if ended:
            evidence.add("end")
        # Veto an explicit continuation, reference reuse, or negated new task.
        # Unlike a global '无参考图' hit, '不要另做无参考图任务' is not a release.
        veto = (
            r"(?:不要|别|不想|不用)(?:再)?(?:结束|停止|取消|另做|另开|重新生成)|"
            r"继续(?:形象照|人像|肖像)|"
            r"(?:继续|仍然|还是)?(?:使用|用|沿用)" + _REF_ZH + "|"
            r"(?:(?:do not|don't|never)\s+(?:end|stop|cancel|create|generate|draw)|"
            r"continue\s+(?:the\s+)?portrait|"
            r"(?:continue\s+using|keep\s+using|reuse|use)\s+" + _REF_EN + ")"
        )
        if re.match(veto, c, re.I):
            evidence.add("keep")
        # A negation applies to the immediately following use/reference object,
        # not to an unrelated new-task verb elsewhere in the same message.
        no_ref = (
            r"(?:(?:不(?:再)?(?:用|使用)|不要(?:再)?(?:用|使用)|别(?:再)?(?:用|使用))" + _REF_ZH + "|"
            r"(?:不要|无)" + _REF_ZH + "|纯文生图|"
            r"(?:do not use|don't use|never use)\s+" + _REF_EN + r"|no\s+" + _REF_EN + ")"
        )
        excluded = bool(re.fullmatch(no_ref + r"[了吧]?", c, re.I))
        if excluded:
            evidence.add("no_ref")
        new = re.match(
            r"(?:另(?:做|开|生成)|重新(?:做|生成)|生成|画一|(?:这是)?全新的独立文生图请求|"
            r"(?:create|generate|draw|make)\b|(?:this is a )?(?:new|separate) (?:independent )?text[ -]to[ -]image request)", c, re.I)
        reference_free_new = False
        if new:
            evidence.add("new")
            # Reference-free modifiers count only inside an affirmative request;
            # embedded negations/conditions are ambiguous, not permission.
            if (not re.search(r"(?:不是|并非|不要|不需要|如果|\bnot\b|\bif\b)", c, re.I)
                    and re.search(r"无参考图|纯文生图|without\s+(?:using\s+)?" + _REF_EN, c, re.I)):
                evidence.add("no_ref")
                reference_free_new = True
        # An unparsed reference/continuation clause is not permission. In
        # particular, a later affirmative reuse cannot be cancelled by an
        # earlier "do not use" clause. Ask for clarification instead.
        reference_mention = (
            r"(?:(?:之前|先前|上传|原来|旧|这张|那张)(?:的)?)+(?:照片|图片)|参考图|原照|上传照|"
            r"(?:(?:previous|old|uploaded|original|reference)\s+)+(?:photos?|images?)\b|\breferences?\b|"
            r"\b(?:with|using|from)\s+" + _REF_EN
        )
        if (not ended and not excluded and not reference_free_new and
                (re.search(reference_mention + r"|形象照|人像|肖像|\bportrait\b", c, re.I)
                 or re.match(r"继续|沿用|(?:continue|reuse|keep using)\b|use\s+(?:it|them|her|him)\b", c, re.I))):
            evidence.add("keep")
    return evidence


def _explicit_new_text_task(msg: dict, blocks: list) -> bool:
    """Only consistent, direct user end + new + no-reference directives release."""
    if msg.get("role") != "user" or any(_upload_id(b) for b in blocks):
        return False
    text = "\n".join(_text_of(b) for b in blocks
                     if isinstance(b, dict) and b.get("type") == "text").strip()
    if not blocks:
        text = str(msg.get("content") or "").strip()
    facts = _task_directives(text)
    return {"end", "new", "no_ref"}.issubset(facts) and "keep" not in facts


def context_from_chat(chat_id: str) -> GenContext:
    """Latest skill start and answered card win. Uploads are those of the current skill run."""
    ctx = GenContext()
    if not chat_id:
        return ctx
    try:
        messages = chat_store.list_messages(chat_id) or []
    except Exception:
        return ctx
    skill_at = -1
    uploads_from = 0
    for i, msg in enumerate(messages):
        blocks = msg.get("blocks") or []
        if not isinstance(blocks, list):
            blocks = []
        # Plain user text can end the current task without selecting another skill.
        # Clear only inferred context, never rewrite stored uploads or tool args.
        if ctx.portrait() and _explicit_new_text_task(msg, blocks):
            ctx = GenContext(skill="text-to-image")
            skill_at = i
            uploads_from = i
        # Skill start: display chip or the provider-text regex if it was stored.
        found_skill = ""
        for b in blocks:
            name = _skill_from_block(b)
            if name:
                found_skill = name
            hit = _SKILL_START_RE.search(_text_of(b))
            if hit:
                found_skill = hit.group(2).strip()
        content = msg.get("content") or msg.get("provider_text") or ""
        if not found_skill and isinstance(content, str):
            hit = _SKILL_START_RE.search(content)
            if hit:
                found_skill = hit.group(2).strip()
        if found_skill:
            ctx.skill = canonical_skill(found_skill)
            skill_at = i
            uploads_from = i
            ctx.uploads = []
            ctx.card = ""
            ctx.answers = None
        # Answered cards: the latest portrait/packaging card of this run (or overall if no skill yet).
        for b in blocks:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "ask" and str(b.get("status") or "") != "answered":
                continue
            kind = _card_kind(b)
            if not kind:
                continue
            # A card after a newer other skill does not apply; a card on/after the
            # current skill start does.
            if skill_at >= 0 and i < skill_at:
                continue
            ctx.card = kind
            ans = b.get("answers")
            ctx.answers = ans if isinstance(ans, dict) else None
        # Uploads that belong to the current skill run (the start message and after).
        if i >= uploads_from:
            for b in blocks:
                uid = _upload_id(b)
                if uid and uid not in ctx.uploads:
                    ctx.uploads.append(uid)
    return ctx


def _portrait_applies(ctx: GenContext, args: dict) -> bool:
    """Current skill/cards, or args.skill when there is no conflicting other skill.

    Agent-supplied skill alone cannot disable a portrait context, and cannot
    enable portrait rules in a different skill's run.
    """
    if ctx.portrait():
        return True
    if ctx.skill and ctx.skill != PORTRAIT:
        return False
    return str((args or {}).get("skill") or "") == PORTRAIT


def _packaging_refs_required(ctx: GenContext) -> bool:
    return ctx.packaging_uses_upload()


def missing_params(args: dict, ctx: GenContext | None = None, *, chat_id: str = "") -> list[str]:
    """Names of required parameters the agent omitted. Never fills them in."""
    ctx = ctx if ctx is not None else context_from_chat(chat_id)
    args = args or {}
    missing: list[str] = []
    has_ref = _has_ref(args)
    # Current portrait task still using the uploaded photo: refs/skill/shot
    # cannot all be omitted (no silent t2i). Never auto-fill the photo or shot.
    uses_photo = ctx.portrait_uses_upload()
    if _portrait_applies(ctx, args) and (has_ref or uses_photo):
        skill = str(args.get("skill") or "").strip()
        shot = _norm_shot(args.get("shot"))
        if skill != PORTRAIT:
            missing.append("skill")
        if shot not in portrait.SHOT_KEYS:
            missing.append("shot")
        if uses_photo and not has_ref:
            missing.append("refs")
    if _packaging_refs_required(ctx) and not has_ref and "refs" not in missing:
        missing.append("refs")
    return missing


def refuse_result(missing: list[str], lang: str | None = None, *, task: str = "") -> dict:
    lang = lang if lang in ("zh", "en") else _lang()
    names = set(missing)
    if names >= {"skill", "shot", "refs"}:
        key = "skill_shot_refs"
    elif "refs" in names and not (names - {"refs"}):
        key = "portrait_refs" if task == "portrait" else "refs"
    elif names >= {"skill", "shot"}:
        key = "skill_shot"
    elif "shot" in names:
        key = "shot"
    else:
        key = "skill"
    text = _ERR[key][lang]
    return {
        "status": "failed",
        "generation_succeeded": False,
        "submitted": False,
        "charged": False,
        "kind": KIND_MISSING,
        "missing": list(missing),
        "lang": lang,
        "error": text,
        "user_message": text,
        "note": text,
    }


def preflight(args: dict, chat_id: str = "") -> dict | None:
    """Refuse dict when required params are missing; None when the call may proceed."""
    ctx = context_from_chat(chat_id)
    missing = missing_params(args, ctx=ctx, chat_id=chat_id)
    if not missing:
        return None
    task = "portrait" if (ctx.portrait() or "skill" in missing or "shot" in missing) else "packaging"
    return refuse_result(missing, task=task)


def _freeze_locks(locks: dict) -> dict:
    frozen = {}
    for key, lock in (locks or {}).items():
        item = {}
        for k, v in (lock or {}).items():
            item[k] = list(v) if isinstance(v, list) else v
        frozen[key] = item
    return frozen


def _restore_locks(locks: dict, frozen: dict) -> None:
    locks.clear()
    for key, lock in (frozen or {}).items():
        item = {}
        for k, v in (lock or {}).items():
            item[k] = list(v) if isinstance(v, list) else v
        locks[key] = item


def preview_locked_args(args: dict) -> dict:
    """The args lock_request would submit, without advancing the turn lock."""
    args = dict(args or {})
    if portrait.applies(args):
        frozen = _freeze_locks(portrait._LOCKS)
        try:
            args = portrait.lock_request(args)
        finally:
            _restore_locks(portrait._LOCKS, frozen)
        args.pop("shot", None)
    if packaging.applies(args):
        frozen = _freeze_locks(packaging._LOCKS)
        try:
            args = packaging.lock_request(args)
        finally:
            _restore_locks(packaging._LOCKS, frozen)
    return args


def prepare_for_quote(args: dict, chat_id: str = "") -> tuple[dict | None, dict | None]:
    """(validated args, None) or (None, refuse result). Loose refs must already be resolved."""
    blocked = preflight(args, chat_id=chat_id)
    if blocked is not None:
        return None, blocked
    return preview_locked_args(args), None
