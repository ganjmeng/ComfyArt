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


def validate_spec(args: dict) -> dict:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    raw_options = args.get("options")
    if not isinstance(raw_options, list) or not (2 <= len(raw_options) <= _MAX_OPTIONS):
        raise ValueError(f"options must be a list of 2..{_MAX_OPTIONS} items")
    options = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(raw_options):
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
        options.append(option)
    min_selections = int(args.get("min_selections") or 1)
    max_selections = int(args.get("max_selections") or 1)
    if not (0 <= min_selections <= max_selections <= len(options)):
        raise ValueError("min/max_selections out of range")
    allow_other = bool(args.get("allow_other"))
    allow_skip = bool(args["allow_skip"]) if "allow_skip" in args else True
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
    spec = {
        "prompt": prompt,
        "options": options,
        "min_selections": min_selections,
        "max_selections": max_selections,
        "allow_other": allow_other,
        "allow_skip": allow_skip,
        "kind": QUESTION_KIND,
    }
    if defaults:
        spec["defaults"] = defaults
    if args.get("page") is not None:
        page = int(args["page"])
        if page < 1:
            raise ValueError("page must be >= 1")
        spec["page"] = page
    if args.get("page_count") is not None:
        page_count = int(args["page_count"])
        if page_count < 1:
            raise ValueError("page_count must be >= 1")
        spec["page_count"] = page_count
    if "page" in spec and "page_count" in spec and spec["page"] > spec["page_count"]:
        raise ValueError("page cannot exceed page_count")
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
                other_text: Optional[str] = None) -> Optional[PendingAsk]:
    ask = PENDING.pop(ask_id, None)
    if ask is None:
        return None
    outcome = {"status": status}
    if selected is not None:
        outcome["selected"] = selected
    if other_text:
        outcome["other_text"] = other_text
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


def validate_answer(spec: dict, selected: list[str],
                    other_text: str) -> None:
    valid_ids = {o["id"] for o in spec["options"]}
    unknown = [s for s in selected if s not in valid_ids]
    if unknown:
        raise ValueError(f"unknown option ids: {unknown}")
    if len(selected) > spec["max_selections"]:
        raise ValueError(f"at most {spec['max_selections']} selections")
    if other_text and not spec["allow_other"]:
        raise ValueError("free-text answer is not allowed for this ask")
    skipping = (
        bool(spec.get("allow_skip"))
        and not selected
        and not other_text
    )
    if skipping:
        return
    if len(selected) < spec["min_selections"] and not (
            other_text and spec["allow_other"]):
        raise ValueError(f"at least {spec['min_selections']} selections")


def skip_note() -> str:
    return _SKIP_NOTE
