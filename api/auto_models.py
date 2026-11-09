"""#133 Auto model choice: when the user names no model, pick one by task type from api/auto_models.json
(product table v1). Deterministic: same prompt -> same category -> same model. User-named models win.

#237: a row matches when any keyword hits, or every term of an ``also`` group hits. English keywords
are whole words ('icon' not in 'iconic'); Chinese keywords are substrings. A hit is ignored when a
negation sits just before it ('no headline', '不要任何文字'). ``exclude`` phrases are blanked first
('portrait orientation', 'job title', 'context menu'). Categories are still first-match, so one
task keeps one model.
"""
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("comfyart")
TABLE = Path(__file__).with_name("auto_models.json")

AUTO_TOKENS = frozenset({"auto", "auto:video"})


def named_or_none(model: str | None) -> str | None:
    """Return a real user-named model id, or None when omitted / explicit Auto (#825).

    Front-end Auto tokens ``auto`` and ``auto:video`` (any case, trimmed) must not win as
    category ``user`` and skip the task table.
    """
    if model is None:
        return None
    s = str(model).strip()
    if not s or s.lower() in AUTO_TOKENS:
        return None
    return s


# Filler between a negation and the keyword: "no headline", "don't add a title", "不要太小的文字".
_NEG_EN = re.compile(r"(?:\bno|without|never|not|don'?t|do not)\b(?:\s+\w+){0,4}\s*$")
# 无 / 别 are single characters and also start unrelated words (无限), so they only count
# immediately before the keyword. The longer negations may take a few characters of filler.
_NEG_ZH = re.compile(r"(?:(?:不要|没有|别加|不加|勿)(?:[\u4e00-\u9fff]{0,4})|(?:无|别)(?:任何)?)$")


def load_table() -> dict:
    with open(TABLE, encoding="utf-8") as f:
        return json.load(f)["features"]


def skill_pin(skill: str | None) -> dict | None:
    """#708: a skill's explicitly registered model row (model, resolution, ratio, fallback), or None."""
    if not skill:
        return None
    with open(TABLE, encoding="utf-8") as f:
        row = (json.load(f).get("skills") or {}).get(str(skill))
    return dict(row) if isinstance(row, dict) else None


def skill_pin_reason(skill: str) -> dict[str, str]:
    """#825 tip category for a skill pin. Mirrors chatMessage.skillPinnedModel (zh/en)."""
    s = str(skill)
    return {"zh": f"{s} 技能固定模型", "en": f"{s} skill pinned model"}


def skill_fallback_choice(skill: str) -> dict:
    """#825: model_choice when a skill's pinned model failed and its registered fallback ran.

    ``model`` is the table fallback (what ran); ``fallback`` is the pinned primary (what failed).
    Reason is the same skill-pin wording as a successful pin — pill_tooltip adds 「 · 首选…」.
    """
    pin = skill_pin(skill)
    if not pin or not pin.get("model") or not pin.get("fallback"):
        raise ValueError(f"skill {skill!r} has no registered model/fallback in auto_models.json")
    fb = pin["fallback"]
    primary = pin["model"]
    return {
        "model": fb,
        "auto": True,
        "category": "skill_fallback",
        "skill": str(skill),
        "fallback": primary,
        "edit_model": fb,
        "resolution": pin.get("resolution"),
        "ratio": pin.get("ratio"),
        "reason": skill_pin_reason(skill),
    }


def tool_feature(tool: str) -> str | None:
    return next((f for f, spec in load_table().items() if spec["tool"] == tool or tool in (spec.get("masked") or {}).get("tools", [])), None)


def _norm(text: str) -> str:
    text = (text or "").lower().replace("–", "-").replace("—", "-").replace("−", "-")
    text = re.sub(r"(?<=[a-z0-9])[-_/](?=[a-z0-9])", " ", text)
    return re.sub(r"\s+", " ", text)


def _spans(keyword: str, text: str):
    k = _norm(keyword)
    if not k:
        return
    if k.isascii():
        for m in re.finditer(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", text):
            yield m.start(), m.end()
        return
    start = 0
    while True:
        i = text.find(k, start)
        if i < 0:
            return
        yield i, i + len(k)
        start = i + len(k)


def hit(keyword: str, text: str) -> bool:
    """English keywords match whole words ('icon' not in 'iconic'); Chinese ones match as substrings."""
    return next(_spans(keyword, _norm(text)), None) is not None


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 18):start]
    return _NEG_EN.search(prefix) is not None or _NEG_ZH.search(prefix) is not None


def _positive(keyword: str, text: str) -> bool:
    return any(not _negated(text, start) for start, _end in _spans(keyword, text))


def _scrub(text: str, phrases: list[str]) -> str:
    chars = list(text)
    for phrase in sorted(phrases or [], key=len, reverse=True):
        for start, end in _spans(phrase, text):
            for i in range(start, end):
                chars[i] = " "
    return "".join(chars)


def _matches(cat: dict, text: str) -> bool:
    text = _scrub(text, cat.get("exclude") or [])
    if any(_positive(k, text) for k in cat.get("keywords") or []):
        return True
    return any(group and all(_positive(k, text) for k in group) for group in cat.get("also") or [])


class UnregisteredModel(ValueError):
    """#712: the table names a model the catalog does not register, and no fallback is registered for it."""


def registered(row: dict, ids: set, where: str) -> tuple[str, str | None]:
    """(model to run, failed model or None). The row's model when the catalog has it; else the first model in the
    row's explicit ``fallback`` list (str or list) that the catalog has, logged. Nothing silent: no registered
    fallback -> UnregisteredModel."""
    model = row["model"]
    if model in ids:
        return model, None
    backups = row.get("fallback") or []
    for alt in [backups] if isinstance(backups, str) else list(backups):
        if alt in ids:
            log.warning("auto model %s for %s not in catalog; using its registered fallback %s", model, where, alt)
            return alt, model
    raise UnregisteredModel(f"auto model {model!r} for {where} is not registered in the model catalog and has no "
                            f"registered fallback in auto_models.json; register it or add a \"fallback\" entry")


def choose(feature: str, prompt: str, named: str | None, catalog: dict, masked: bool = False) -> dict:
    """catalog: load_config() result. Returns {model, auto, category, reason: {zh, en}}.
    masked (#45): the edit has a selection or brushed mask -> the table's 'masked' row (user-named still wins).
    #825: ``auto`` / ``auto:video`` are not user picks — they consult the table like an omitted model."""
    cfg = catalog["features"][feature]
    named = named_or_none(named)
    if named:
        return {"model": named, "auto": False, "category": "user",
                "reason": {"zh": "你指定了这个模型", "en": "you named this model"}}
    spec = load_table()[feature]
    row = spec.get("masked") if masked else None
    ids = {m["id"] for m in cfg["models"]}
    if row:
        model, failed = registered(row, ids, f"{feature}/masked")
        out = {"model": model, "auto": True, "category": "masked", "reason": {"zh": row["zh"], "en": row["en"]}}
        return {**out, "fallback": failed} if failed else out
    text = _norm(prompt or "")
    cat = next((c for c in spec["categories"] if _matches(c, text)), None)
    if cat and cat["model"] not in ids:
        # #712: only an explicitly registered fallback may stand in; otherwise registered() raises
        model, failed = registered(cat, ids, f"{feature}/{cat['id']}")
        return {"model": model, "auto": True, "category": cat["id"], "fallback": failed,
                "reason": {"zh": f"{cat['zh']}，{failed} 未登记，按登记的备选改用 {model}",
                           "en": f"{cat['en']}; {failed} is not registered, so its registered fallback {model} was used"}}
    if cat:
        return {"model": cat["model"], "auto": True, "category": cat["id"], "reason": {"zh": cat["zh"], "en": cat["en"]}}
    return {"model": cfg["default"], "auto": True, "category": "default", "reason": dict(spec["default"]), "plain": True}


def note(choice: dict) -> str:
    """One line the agent repeats in its reply: 用了 X，因为 Y / used X because Y."""
    m, r = choice["model"], choice["reason"]
    if choice.get("plain"):
        return f"用了 {m}，{r['zh']}。/ Used {m}, {r['en']}."
    return f"用了 {m}，因为{r['zh']}。/ Used {m} because {r['en']}."


# Short labels for the generation-card Auto pill (#825). Prefer catalog label when the UI has it;
# these fallbacks keep tooltips readable without loading the WaveSpeed catalog.
_SHORT = {
    "openai/gpt-image-2.6-sunburst/text-to-image": "GPT Image 2.6 Sunburst",
    "openai/gpt-image-2.6-sunburst/edit": "GPT Image 2.6 Sunburst",
    "openai/gpt-image-2.6-flare/text-to-image": "GPT Image 2.6 Flare",
    "openai/gpt-image-2.6-flare/edit": "GPT Image 2.6 Flare",
    "openai/gpt-image-2.5-sunburst/edit": "GPT Image 2.5 Sunburst",
    "openai/gpt-image-2.5-flare/text-to-image": "GPT Image 2.5 Flare",
    "openai/gpt-image-2.5-flare/edit": "GPT Image 2.5 Flare",
    "google/nano-banana-2.1/text-to-image": "Nano Banana 2.1",
    "google/nano-banana-2.1/edit": "Nano Banana 2.1",
    "google/nano-banana-pro/edit": "Nano Banana Pro",
    "bytedance/seedream-v5.0-pro": "Seedream 5.0 Pro",
    "bytedance/seedream-v5.0-pro/edit": "Seedream 5.0 Pro",
    "recraft-ai/recraft-v3": "Recraft V3",
}


_ACRONYMS = frozenset({"gpt", "ai", "ui", "io", "api", "cpu", "gpu", "vae"})


def _humanize_id_segment(seg: str) -> str:
    """Hyphen/underscore → spaces; capitalize words but keep known acronyms (GPT not Gpt)."""
    words = seg.replace("-", " ").replace("_", " ").split()
    out: list[str] = []
    for w in words:
        low = w.lower()
        if low in _ACRONYMS:
            out.append(low.upper())
        elif w:
            out.append(w[0].upper() + w[1:])
        else:
            out.append(w)
    return " ".join(out)


def short_name(model: str | None) -> str:
    """Human short name for a WaveSpeed model id (pill text)."""
    if not model:
        return ""
    if model in _SHORT:
        return _SHORT[model]
    # owner/name[/variant] → slug segment, humanized without mangling GPT→Gpt
    parts = [p for p in str(model).split("/") if p]
    if len(parts) >= 2:
        return _humanize_id_segment(parts[-2])
    return str(model)


def reason_text(choice: dict, lang: str = "zh") -> str:
    """Locale string from the routing table reason (no separate frontend copy)."""
    r = choice.get("reason") or {}
    if not isinstance(r, dict):
        return str(r or "")
    key = "en" if str(lang).lower().startswith("en") else "zh"
    return str(r.get(key) or r.get("zh") or r.get("en") or "")


def pill_label(choice: dict, *, catalog_label: str | None = None) -> str | None:
    """Visible pill text. Auto → 'Auto · <name>'; manual → model name only; None when no model yet.

    Before the actual model is known, callers should pass choice={'auto': True} with no model → 'Auto'.
    Legacy cards with neither model nor auto → None (render nothing).
    """
    if not isinstance(choice, dict):
        return None
    model = choice.get("model")
    auto = bool(choice.get("auto"))
    name = (catalog_label or "").strip() or short_name(model)
    if auto and not model:
        return "Auto"
    if not model and not auto:
        return None
    if auto:
        # fallback used: still Auto prefix; tooltip explains 首选 X 失败
        return f"Auto · {name}" if name else "Auto"
    return name or None


# Mirrors src/locales chatMessage.autoPickedPrefix (i18n owns the string; keep in sync).
_AUTO_PICKED_PREFIX = {"zh": "自动选择：", "en": "Auto-picked: "}


def pill_tooltip(choice: dict, lang: str = "zh") -> str | None:
    """Hover/tap reason. Manual picks: None (UI shows no reason popup).

    Auto (table): i18n prefix + table category.
    Skill pin / skill fallback: NO auto-picked prefix — skill wording only.
    Fallback (any): ``{category} · 首选 X 失败，改用 Y`` (preferred = choice['fallback']).
    """
    if not isinstance(choice, dict) or not choice.get("auto"):
        return None
    en = str(lang).lower().startswith("en")
    key = "en" if en else "zh"
    skillish = bool(choice.get("skill")) or choice.get("category") in ("skill", "skill_fallback")
    prefix = "" if skillish else _AUTO_PICKED_PREFIX[key]
    category = reason_text(choice, key)
    failed = choice.get("fallback")
    model = choice.get("model")
    if failed and model:
        if en:
            body = f"{category} · Preferred {short_name(failed)} failed, used {short_name(model)}"
        else:
            body = f"{category} · 首选 {short_name(failed)} 失败，改用 {short_name(model)}"
        return f"{prefix}{body}".strip()
    if not category:
        return None
    return f"{prefix}{category}"
