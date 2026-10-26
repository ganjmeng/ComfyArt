import asyncio
import uuid
from typing import Optional

ASK_TIMEOUT_S = 540.0
RUN_APPROVAL_WAIT_S = 45.0
RUN_APPROVAL_KIND = "run_approval"
QUESTION_KIND = "question"

_MAX_OPTIONS = 12
_SKIP_NOTE = (
    "user skipped this question; continue with sensible defaults or omit "
    "this preference — do not re-ask immediately"
)


class PendingAsk:
    def __init__(self, chat_id: str, message_id: str, spec: dict) -> None:
        self.id = uuid.uuid4().hex
        self.chat_id = chat_id
        self.message_id = message_id
        self.spec = spec
        self.abandoned = False
        self.future: asyncio.Future = asyncio.get_event_loop().create_future()


PENDING: dict[str, PendingAsk] = {}
ANSWERED_RUN_APPROVALS: dict[tuple[str, str], dict] = {}


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


def validate_spec(args: dict) -> dict:
    """Accept legacy single-question OR questions[] multi form."""
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
    return ask


def take_run_approval_answer(chat_id: str, prompt: str) -> Optional[dict]:
    return ANSWERED_RUN_APPROVALS.pop((chat_id, prompt), None)


def abandon_ask(ask_id: str) -> None:
    ask = PENDING.get(ask_id)
    if ask is not None:
        ask.abandoned = True


def resolve_ask(ask_id: str, status: str,
                selected: Optional[list[str]] = None,
                other_text: Optional[str] = None,
                answers: Optional[dict] = None) -> Optional[PendingAsk]:
    ask = PENDING.pop(ask_id, None)
    if ask is None:
        return None
    outcome: dict = {"status": status}
    if selected is not None:
        outcome["selected"] = selected
    if other_text:
        outcome["other_text"] = other_text
    if answers is not None:
        outcome["answers"] = answers
    nobody_waiting = ask.future.done() or ask.abandoned
    if nobody_waiting and status == "answered" and is_run_approval(ask.spec):
        ANSWERED_RUN_APPROVALS[(ask.chat_id, str(ask.spec.get("prompt") or ""))] = outcome
    if not ask.future.done():
        ask.future.set_result(outcome)
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

