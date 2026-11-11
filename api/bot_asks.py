import asyncio
import logging
import time
import uuid
from typing import Optional

from ..bot import bot_asks as _kit
from ..bot.run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID
from .ask_store import get_store, stamp_ownership

# Kit base layer (bot/bot_asks.py) owns the shared constants and the single
# PENDING store; this module extends it (persistence, multi-question specs).
ASK_TIMEOUT_S = _kit.ASK_TIMEOUT_S
RUN_APPROVAL_WAIT_S = _kit.RUN_APPROVAL_WAIT_S
RUN_APPROVAL_KIND = _kit.RUN_APPROVAL_KIND
QUESTION_KIND = "question"

_MAX_OPTIONS = 12
# After ask_user resolves: default is continue the original task immediately
# (generate when appropriate). Do NOT emit a separate pre-generate
# confirmation sentence. Restate the choice in the post-image completion
# intro. Wait/no-generate prose only if the user explicitly asked to wait.
# Do not say "continue with sensible defaults".
_SKIP_NOTE = (
    "user skipped this question; do NOT write a separate pre-generate "
    "confirmation (no Got it / 知道了 skip line before images). Immediately "
    "continue the user's original task (generation expected when they did "
    "not ask to wait). Only if their own instructions asked you to wait or "
    "not generate yet, use the pinned wait sentences and do not generate "
    "this turn — do not re-ask immediately"
)
_ANSWER_NOTE = (
    "user answered; do NOT write a separate pre-generate confirmation "
    "(no Got it / 知道了 restating the choice before images). Immediately "
    "continue the user's original task — generation is expected and "
    "required when they did not ask to wait. After images are delivered, "
    "restate their selection in the completion intro and invite "
    "adjustments. Only if their own instructions asked you to wait or not "
    "generate yet, use the pinned wait sentences and do not generate this "
    "turn"
)


log = logging.getLogger("comfyart.bot_asks")


class PendingAsk(_kit.PendingAsk):
    # Does not call the kit __init__: ours adds ownership and a lazy future.
    def __init__(
        self,
        chat_id: str,
        message_id: str,
        spec: dict,
        *,
        ask_id: Optional[str] = None,
        abandoned: bool = False,
        owner_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        project_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ) -> None:
        self.id = ask_id or uuid.uuid4().hex
        self.chat_id = chat_id
        self.message_id = message_id
        self.spec = spec
        self.abandoned = abandoned
        self.owner_id = owner_id or LOCAL_OWNER_ID
        self.workspace_id = workspace_id or LOCAL_WORKSPACE_ID
        self.project_id = project_id or LOCAL_PROJECT_ID
        self.created_at = created_at if created_at is not None else time.time()
        self._future: Optional[asyncio.Future] = None

    @property
    def future(self) -> asyncio.Future:
        # Lazy: reload-at-import must not require a running event loop.
        if self._future is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            self._future = loop.create_future()
        return self._future

    def future_done(self) -> bool:
        return self._future is not None and self._future.done()

    def to_record(self) -> dict:
        return stamp_ownership({
            "id": self.id,
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "spec": self.spec,
            "owner_id": self.owner_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
        })

    @classmethod
    def from_record(cls, rec: dict, *, abandoned: bool = True) -> "PendingAsk":
        stamped = stamp_ownership(rec)
        return cls(
            chat_id=str(stamped["chat_id"]),
            message_id=str(stamped.get("message_id") or ""),
            spec=dict(stamped.get("spec") or {}),
            ask_id=str(stamped["id"]),
            abandoned=abandoned,
            owner_id=stamped.get("owner_id"),
            workspace_id=stamped.get("workspace_id"),
            project_id=stamped.get("project_id"),
            created_at=stamped.get("created_at"),
        )


PENDING: dict[str, PendingAsk] = _kit.PENDING
ANSWERED_RUN_APPROVALS: dict[tuple[str, str], dict] = _kit.ANSWERED_RUN_APPROVALS


def _store_put(ask: PendingAsk) -> None:
    try:
        get_store().put(ask.to_record())
    except OSError as e:
        log.warning("ask store put failed for %s: %s", ask.id, e)


def _store_delete(ask_id: str) -> None:
    try:
        get_store().delete(ask_id)
    except OSError as e:
        log.warning("ask store delete failed for %s: %s", ask_id, e)


def _parse_option(raw: dict, i: int, seen_ids: set[str]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"options[{i}] must be an object")
    oid = str(raw.get("id") or "").strip()
    label = str(raw.get("label") or "").strip()
    if not oid or not label:
        raise ValueError(f"options[{i}] needs id and label")
    if oid in seen_ids:
        raise ValueError(f"duplicate option id {oid!r}")
    seen_ids.add(oid)
    option = {"id": oid, "label": label}
    if raw.get("description"):
        option["description"] = str(raw["description"])
    if raw.get("recommended"):
        option["recommended"] = True
    return option


def _parse_question(raw: dict, index: int) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"questions[{index}] must be an object")
    qid = str(raw.get("id") or "").strip()
    prompt = str(raw.get("prompt") or "").strip()
    if not qid or not prompt:
        raise ValueError(f"questions[{index}] needs id and prompt")
    raw_options = raw.get("options") or []
    if not isinstance(raw_options, list):
        raise ValueError(f"questions[{index}].options must be a list")
    allow_other = bool(raw.get("allow_other"))
    # Text-only: no options + allow_other. Choice: 2..12 options.
    if not raw_options:
        if not allow_other:
            raise ValueError(
                f"questions[{index}] needs options (2..{_MAX_OPTIONS}) "
                "or allow_other for free text"
            )
        options: list[dict] = []
        seen: set[str] = set()
    else:
        if not (2 <= len(raw_options) <= _MAX_OPTIONS):
            raise ValueError(
                f"questions[{index}].options must be a list of "
                f"2..{_MAX_OPTIONS} items"
            )
        seen = set()
        options = [_parse_option(o, i, seen) for i, o in enumerate(raw_options)]
    min_selections = int(raw.get("min_selections") or (0 if not options else 1))
    max_selections = int(raw.get("max_selections") or (0 if not options else 1))
    if options:
        if not (0 <= min_selections <= max_selections <= len(options)):
            raise ValueError(f"questions[{index}] min/max_selections out of range")
    else:
        min_selections = 0
        max_selections = 0
    defaults: list[str] = []
    raw_defaults = raw.get("defaults")
    if raw_defaults is not None:
        if not isinstance(raw_defaults, list):
            raise ValueError(f"questions[{index}].defaults must be a list")
        defaults = [str(d) for d in raw_defaults]
        unknown = [d for d in defaults if d not in seen]
        if unknown:
            raise ValueError(f"questions[{index}] unknown default ids: {unknown}")
        if len(defaults) > max_selections:
            raise ValueError(f"questions[{index}] defaults exceed max_selections")
    elif any(o.get("recommended") for o in options):
        defaults = [o["id"] for o in options if o.get("recommended")][:max_selections]
    page = int(raw["page"]) if raw.get("page") is not None else 1
    if page < 1:
        raise ValueError(f"questions[{index}].page must be >= 1")
    q: dict = {
        "id": qid,
        "prompt": prompt,
        "options": options,
        "min_selections": min_selections,
        "max_selections": max_selections,
        "allow_other": allow_other,
        "page": page,
    }
    if defaults:
        q["defaults"] = defaults
    if raw.get("placeholder"):
        q["placeholder"] = str(raw["placeholder"])
    return q



# #911 studio-model direction card: enforce only the card SKELETON in code.
# Options stay whatever the model generated from the garment; do not write
# option labels or append （推荐） here (that stays in the skill template).
# Matched by the locked title or id so a legacy prompt+options call (which
# would otherwise get id "_") is rewritten the same way.
STUDIO_DIRECTION_PROMPT = "选一个棚拍方向继续生成："
STUDIO_DIRECTION_ID = "studio_direction"
STUDIO_DIRECTION_PLACEHOLDER = "以上都不符合，我自己描述方向…"


def _is_studio_direction_question(raw: dict) -> bool:
    if not isinstance(raw, dict):
        return False
    qid = str(raw.get("id") or "").strip()
    prompt = str(raw.get("prompt") or "").strip()
    return qid == STUDIO_DIRECTION_ID or prompt == STUDIO_DIRECTION_PROMPT


def _skeleton_studio_direction_question(raw: dict) -> dict:
    """Force id, title, free-text row. Leave options / recommended / defaults alone."""
    q = dict(raw)
    q["id"] = STUDIO_DIRECTION_ID
    q["prompt"] = STUDIO_DIRECTION_PROMPT
    q["allow_other"] = True
    q["placeholder"] = STUDIO_DIRECTION_PLACEHOLDER
    q["page"] = 1
    return q


def normalize_studio_direction_card(args: dict) -> dict:
    """Force direction-card skeleton: id, title, other-row placeholder, Skip/Submit footer."""
    args = dict(args or {})
    questions = args.get("questions")
    touched = False
    if isinstance(questions, list) and questions:
        new_questions = []
        for q in questions:
            if _is_studio_direction_question(q) if isinstance(q, dict) else False:
                new_questions.append(_skeleton_studio_direction_question(q))
                touched = True
            else:
                new_questions.append(q)
        if touched:
            args["questions"] = new_questions
            args["allow_skip"] = True
            args["page_count"] = 1
            args["allow_other"] = True
            first = new_questions[0]
            if isinstance(first, dict) and first.get("id") == STUDIO_DIRECTION_ID:
                args["prompt"] = STUDIO_DIRECTION_PROMPT
                if "options" in first:
                    args["options"] = first.get("options")
        return args
    if (
        str(args.get("prompt") or "").strip() == STUDIO_DIRECTION_PROMPT
        or str(args.get("id") or "").strip() == STUDIO_DIRECTION_ID
    ):
        question = _skeleton_studio_direction_question({
            "id": STUDIO_DIRECTION_ID,
            "prompt": args.get("prompt") or STUDIO_DIRECTION_PROMPT,
            "options": args.get("options") or [],
            "allow_other": True,
            "placeholder": STUDIO_DIRECTION_PLACEHOLDER,
            "page": args.get("page") or 1,
            **({"min_selections": args["min_selections"]} if "min_selections" in args else {}),
            **({"max_selections": args["max_selections"]} if "max_selections" in args else {}),
        })
        args["questions"] = [question]
        args["prompt"] = STUDIO_DIRECTION_PROMPT
        args["options"] = question.get("options")
        args["allow_other"] = True
        args["page_count"] = 1
        args["allow_skip"] = True
    return args



# #911 clothing-swap: enforce only the card SKELETON in code.
# Question title and option labels stay live (from the person outfit / garment);
# do not copy a fixture-specific wording such as 宝蓝T恤. Matched by the locked
# id or a how-to-replace-upper-body prompt so a legacy prompt+options call is
# rewritten the same way.
CLOTHING_SWAP_QUESTION_ID = "upper_body_swap"
CLOTHING_SWAP_PROMPT_FALLBACK = "这件衣服要怎么替换模特的上身？"
CLOTHING_SWAP_PLACEHOLDER = "其它穿法，我来说呢..."
_CLOTHING_SWAP_DROP_IDS = frozenset({
    "gender", "ethnicity", "angle", "angles", "shot", "shot_size", "shot-size",
})


def _is_clothing_swap_question(raw: dict) -> bool:
    if not isinstance(raw, dict):
        return False
    qid = str(raw.get("id") or "").strip()
    prompt = str(raw.get("prompt") or "").strip()
    if qid == CLOTHING_SWAP_QUESTION_ID:
        return True
    # Structural how-to-replace-the-top question (live title may name the garment).
    # Do not match studio-model "由哪种性别的模特上身？" (has 上身, no 怎么替换).
    if "怎么替换" in prompt and ("上身" in prompt or "上衣" in prompt):
        return True
    low = prompt.lower()
    if "how" in low and "replace" in low and any(
        w in low for w in ("upper", "upper-body", "upper body", "top", "t-shirt", "tee")
    ):
        return True
    return False


def _is_clothing_swap_forbidden_extra(raw: object) -> bool:
    """Gender / ethnicity / angle questions must not ride along with the swap card."""
    if not isinstance(raw, dict):
        return False
    qid = str(raw.get("id") or "").strip().casefold()
    if qid in _CLOTHING_SWAP_DROP_IDS:
        return True
    prompt = str(raw.get("prompt") or "")
    low = prompt.lower()
    if any(n in prompt for n in ("性别", "族裔", "角度")):
        return True
    if any(n in low for n in ("gender", "ethnicity", "ethnic", "angle", "shot size", "shot-size")):
        return True
    return False


def _skeleton_clothing_swap_question(raw: dict) -> dict:
    """Force id, free-text row, nothing preselected. Leave live prompt + option labels."""
    q = dict(raw)
    q["id"] = CLOTHING_SWAP_QUESTION_ID
    if not str(q.get("prompt") or "").strip():
        q["prompt"] = CLOTHING_SWAP_PROMPT_FALLBACK
    q["allow_other"] = True
    q["placeholder"] = CLOTHING_SWAP_PLACEHOLDER
    q["page"] = 1
    q.pop("defaults", None)
    opts = q.get("options")
    if isinstance(opts, list):
        cleaned = []
        for o in opts:
            if isinstance(o, dict):
                item = dict(o)
                item.pop("recommended", None)
                cleaned.append(item)
            else:
                cleaned.append(o)
        q["options"] = cleaned
    return q


def normalize_clothing_swap_card(args: dict) -> dict:
    """Force a single how-to-swap-the-top card: id, other-row, no preselect, no extras."""
    args = dict(args or {})
    questions = args.get("questions")
    if isinstance(questions, list) and questions:
        if not any(_is_clothing_swap_question(q) for q in questions if isinstance(q, dict)):
            return args
        kept = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            if _is_clothing_swap_forbidden_extra(q):
                continue
            if _is_clothing_swap_question(q):
                kept.append(_skeleton_clothing_swap_question(q))
            # Drop anything else on this card so it stays ONE question.
        if not kept:
            return args
        first = kept[0]
        args["questions"] = [first]
        args["allow_skip"] = True
        args["page_count"] = 1
        args["allow_other"] = True
        args["prompt"] = first.get("prompt")
        if "options" in first:
            args["options"] = first.get("options")
        args.pop("defaults", None)
        return args
    if _is_clothing_swap_question(args) or str(args.get("id") or "").strip() == CLOTHING_SWAP_QUESTION_ID:
        question = _skeleton_clothing_swap_question({
            "id": args.get("id") or CLOTHING_SWAP_QUESTION_ID,
            "prompt": args.get("prompt") or CLOTHING_SWAP_PROMPT_FALLBACK,
            "options": args.get("options") or [],
            "allow_other": True,
            "placeholder": CLOTHING_SWAP_PLACEHOLDER,
            "page": args.get("page") or 1,
            **({"min_selections": args["min_selections"]} if "min_selections" in args else {}),
            **({"max_selections": args["max_selections"]} if "max_selections" in args else {}),
        })
        args["questions"] = [question]
        args["prompt"] = question.get("prompt")
        args["options"] = question.get("options")
        args["allow_other"] = True
        args["page_count"] = 1
        args["allow_skip"] = True
        args.pop("defaults", None)
    return args


def validate_spec(args: dict) -> dict:
    """Accept legacy single-question OR questions[] multi form."""
    args = normalize_clothing_swap_card(args)
    args = normalize_studio_direction_card(args)
    allow_skip = bool(args["allow_skip"]) if "allow_skip" in args else True
    raw_questions = args.get("questions")
    if raw_questions is not None:
        if not isinstance(raw_questions, list) or not raw_questions:
            raise ValueError("questions must be a non-empty list")
        questions = [_parse_question(q, i) for i, q in enumerate(raw_questions)]
        ids = [q["id"] for q in questions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate question ids")
        page_count = int(args["page_count"]) if args.get("page_count") is not None else max(
            (q["page"] for q in questions), default=1
        )
        if page_count < 1:
            raise ValueError("page_count must be >= 1")
        if any(q["page"] > page_count for q in questions):
            raise ValueError("question page cannot exceed page_count")
        # Top-level prompt mirrors first question for notify / legacy readers.
        spec = {
            "prompt": questions[0]["prompt"],
            "options": questions[0]["options"],
            "min_selections": questions[0]["min_selections"],
            "max_selections": questions[0]["max_selections"],
            "allow_other": questions[0]["allow_other"],
            "allow_skip": allow_skip,
            "kind": QUESTION_KIND,
            "questions": questions,
            "page_count": page_count,
        }
        if questions[0].get("defaults"):
            spec["defaults"] = questions[0]["defaults"]
        return spec

    # Legacy single-question shape.
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required (or pass questions[])")
    raw_options = args.get("options")
    if not isinstance(raw_options, list) or not (2 <= len(raw_options) <= _MAX_OPTIONS):
        raise ValueError(f"options must be a list of 2..{_MAX_OPTIONS} items")
    seen_ids: set[str] = set()
    options = [_parse_option(raw, i, seen_ids) for i, raw in enumerate(raw_options)]
    min_selections = int(args.get("min_selections") or 1)
    max_selections = int(args.get("max_selections") or 1)
    if not (0 <= min_selections <= max_selections <= len(options)):
        raise ValueError("min/max_selections out of range")
    allow_other = bool(args.get("allow_other"))
    defaults: list[str] = []
    raw_defaults = args.get("defaults")
    if raw_defaults is not None:
        if not isinstance(raw_defaults, list):
            raise ValueError("defaults must be a list of option ids")
        defaults = [str(d) for d in raw_defaults]
        unknown = [d for d in defaults if d not in seen_ids]
        if unknown:
            raise ValueError(f"unknown default ids: {unknown}")
        if len(defaults) > max_selections:
            raise ValueError(f"defaults exceed max_selections ({max_selections})")
    elif any(o.get("recommended") for o in options):
        defaults = [o["id"] for o in options if o.get("recommended")][:max_selections]
    question = {
        "id": "_",
        "prompt": prompt,
        "options": options,
        "min_selections": min_selections,
        "max_selections": max_selections,
        "allow_other": allow_other,
        "page": 1,
    }
    if defaults:
        question["defaults"] = defaults
    page_count = int(args["page_count"]) if args.get("page_count") is not None else 1
    if page_count < 1:
        raise ValueError("page_count must be >= 1")
    page = int(args["page"]) if args.get("page") is not None else 1
    if page < 1:
        raise ValueError("page must be >= 1")
    if page > page_count:
        raise ValueError("page cannot exceed page_count")
    question["page"] = page
    spec = {
        "prompt": prompt,
        "options": options,
        "min_selections": min_selections,
        "max_selections": max_selections,
        "allow_other": allow_other,
        "allow_skip": allow_skip,
        "kind": QUESTION_KIND,
        "questions": [question],
        "page_count": page_count,
    }
    if defaults:
        spec["defaults"] = defaults
    if args.get("page") is not None:
        spec["page"] = page
    return spec


def is_run_approval(spec: dict) -> bool:
    return (spec or {}).get("kind") == RUN_APPROVAL_KIND


def create_ask(chat_id: str, message_id: str, spec: dict) -> PendingAsk:
    if is_run_approval(spec):
        for stale in [a for a in PENDING.values()
                      if a.chat_id == chat_id and is_run_approval(a.spec)]:
            resolve_ask(stale.id, "cancelled")
    ask = PendingAsk(chat_id, message_id, spec)
    PENDING[ask.id] = ask
    _store_put(ask)
    return ask


def take_run_approval_answer(chat_id: str, prompt: str) -> Optional[dict]:
    return ANSWERED_RUN_APPROVALS.pop((chat_id, prompt), None)


def abandon_ask(ask_id: str) -> None:
    ask = PENDING.get(ask_id)
    if ask is not None:
        ask.abandoned = True
    # AC4: abandoned asks must not resurrect after restart — delete store row,
    # keep PENDING so an in-process answer (e.g. late run_approval) still works.
    _store_delete(ask_id)


def resolve_ask(ask_id: str, status: str,
                selected: Optional[list[str]] = None,
                other_text: Optional[str] = None,
                answers: Optional[dict] = None) -> Optional[PendingAsk]:
    ask = PENDING.pop(ask_id, None)
    if ask is None:
        return None
    _store_delete(ask_id)
    outcome: dict = {"status": status}
    if selected is not None:
        outcome["selected"] = selected
    if other_text:
        outcome["other_text"] = other_text
    if answers is not None:
        outcome["answers"] = answers
    nobody_waiting = ask.future_done() or ask.abandoned
    if nobody_waiting and status == "answered" and is_run_approval(ask.spec):
        ANSWERED_RUN_APPROVALS[(ask.chat_id, str(ask.spec.get("prompt") or ""))] = outcome
    # Complete an existing waiter; do not create a Future just to mark done
    # (sync callers / abandoned reloads have no event loop).
    if ask._future is not None and not ask._future.done():
        ask._future.set_result(outcome)
    elif ask._future is None and not ask.abandoned:
        try:
            ask.future.set_result(outcome)
        except RuntimeError:
            pass
    return ask


def cancel_chat_asks(chat_id: str) -> list[PendingAsk]:
    stale = [a for a in PENDING.values()
             if a.chat_id == chat_id and not is_run_approval(a.spec)]
    return [ask for a in stale
            if (ask := resolve_ask(a.id, "cancelled")) is not None]


def _validate_one_answer(q: dict, selected: list[str], other_text: str,
                         *, allow_skip_empty: bool) -> None:
    valid_ids = {o["id"] for o in q["options"]}
    unknown = [s for s in selected if s not in valid_ids]
    if unknown:
        raise ValueError(f"unknown option ids: {unknown}")
    if len(selected) > q["max_selections"]:
        raise ValueError(f"at most {q['max_selections']} selections")
    if other_text and not q["allow_other"]:
        raise ValueError("free-text answer is not allowed for this ask")
    if allow_skip_empty and not selected and not other_text:
        return
    if len(selected) < q["min_selections"] and not (
            other_text and q["allow_other"]):
        raise ValueError(f"at least {q['min_selections']} selections")
    if not q["options"] and q["allow_other"] and not other_text and not allow_skip_empty:
        raise ValueError("text answer required")


def validate_answer(spec: dict, selected: list[str],
                    other_text: str,
                    answers: Optional[dict] = None) -> None:
    questions = spec.get("questions")
    skipping = (
        bool(spec.get("allow_skip"))
        and not selected
        and not other_text
        and not answers
    )
    if skipping:
        return
    if answers is not None:
        if not isinstance(answers, dict):
            raise ValueError("answers must be an object")
        if not questions:
            raise ValueError("answers require questions[] in the spec")
        by_id = {q["id"]: q for q in questions}
        # Whole-ask skip: empty map, or every answer empty, when allow_skip.
        if bool(spec.get("allow_skip")) and not selected and not other_text:
            if not answers:
                return
            all_empty = True
            for qid, ans in answers.items():
                if qid not in by_id:
                    raise ValueError(f"unknown question id {qid!r}")
                if not isinstance(ans, dict):
                    raise ValueError(f"answers[{qid}] must be an object")
                if (ans.get("selected") or []) or ans.get("other_text"):
                    all_empty = False
                    break
            if all_empty and set(answers) <= set(by_id):
                return
        missing = [q["id"] for q in questions if q["id"] not in answers]
        if missing:
            raise ValueError(f"missing answers for: {missing}")
        for qid, ans in answers.items():
            if qid not in by_id:
                raise ValueError(f"unknown question id {qid!r}")
            if not isinstance(ans, dict):
                raise ValueError(f"answers[{qid}] must be an object")
            sel = [str(s) for s in (ans.get("selected") or [])]
            oth = str(ans.get("other_text") or "")
            _validate_one_answer(by_id[qid], sel, oth, allow_skip_empty=False)
        return
    # Legacy single selected/other_text against top-level fields (validate_spec
    # mirrors questions[0] there; callers may override e.g. allow_other=False).
    q = {
        "options": list(spec.get("options") or ((questions or [{}])[0].get("options") or [])),
        "min_selections": int(spec["min_selections"]),
        "max_selections": int(spec["max_selections"]),
        "allow_other": bool(spec["allow_other"]),
    }
    _validate_one_answer(
        q, selected, other_text,
        allow_skip_empty=bool(spec.get("allow_skip")),
    )


def skip_note() -> str:
    return _SKIP_NOTE


def answer_note() -> str:
    return _ANSWER_NOTE


def list_pending_for_chat(chat_id: str) -> list[PendingAsk]:
    return [a for a in PENDING.values() if a.chat_id == chat_id]


def pending_ask_to_block(ask: PendingAsk) -> dict:
    """Serialize a live/restored ask as a chat `ask` block for the frontend."""
    return {
        "type": "ask",
        "ask_id": ask.id,
        "message_id": ask.message_id,
        "status": "pending",
        **ask.spec,
    }


def reload_pending_from_store() -> int:
    """Rehydrate PENDING from disk. Restored rows are abandoned (no live agent waiter).

    Clears the in-memory table first so a second call (tests / mid-run) does not
    duplicate. Returns how many asks were loaded.
    """
    PENDING.clear()
    n = 0
    for rec in get_store().list_all():
        try:
            ask = PendingAsk.from_record(rec, abandoned=True)
        except (KeyError, TypeError, ValueError) as e:
            log.warning("skip corrupt ask record: %s", e)
            continue
        PENDING[ask.id] = ask
        n += 1
    return n

