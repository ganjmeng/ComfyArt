"""#390-1: rolling model-written summary of old turns, cached behind a small storage interface.

Stored data is keyed by workspace_id + owner_id + project_id (single-user defaults today), so a
database can replace the in-memory store later without touching callers. State lives server-side.
"""
from __future__ import annotations

import asyncio
import hashlib
import threading
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

from .run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID

# System-layer defaults (settings may override later).
DEFAULTS = {
    "summary_timeout_s": 20.0,   # one summary call; timeout / error = rule summary, nothing cached
}


# ---------------------------------------------------------------------------
# Storage interface
# ---------------------------------------------------------------------------
class KeyValueStore(ABC):
    @abstractmethod
    def get(self, ns: str, key: str, *, workspace_id: str, owner_id: str,
            project_id: str) -> Optional[str]: ...

    @abstractmethod
    def put(self, ns: str, key: str, value: str, *, workspace_id: str, owner_id: str,
            project_id: str) -> None: ...


class MemoryKeyValueStore(KeyValueStore):
    """Process-local, bounded (oldest entry dropped first), thread-safe."""

    def __init__(self, max_items: int = 512) -> None:
        self._data: dict[tuple, str] = {}
        self._max = max_items
        self._lock = threading.Lock()

    def get(self, ns, key, *, workspace_id, owner_id, project_id):
        with self._lock:
            return self._data.get((workspace_id, owner_id, project_id, ns, key))

    def put(self, ns, key, value, *, workspace_id, owner_id, project_id):
        with self._lock:
            k = (workspace_id, owner_id, project_id, ns, key)
            if k not in self._data and len(self._data) >= self._max:
                self._data.pop(next(iter(self._data)))
            self._data[k] = value


_STORE: KeyValueStore = MemoryKeyValueStore()


def get_store() -> KeyValueStore:
    return _STORE


def set_store(store: KeyValueStore) -> None:
    global _STORE
    _STORE = store


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 1. Model-written summary of old turns
# ---------------------------------------------------------------------------
PROMPT_VERSION = "v1"  # bump when SUMMARY_PROMPT changes: old cache entries stop matching
SUMMARY_PROMPT = (
    "You maintain a running summary of an earlier conversation for an assistant that continues it. "
    "You get the previous summary (may be empty) and the turns that just left the context. Return the "
    "updated summary. Always keep these five sections, as short bullet lines:\n"
    "Goals: what the user wants overall.\n"
    "Requirements: counts, sizes, ratios, styles, budget and other constraints.\n"
    "Decisions: choices already made (models, prompts, layout) and anything the user approved or rejected.\n"
    "Canvas objects: shape ids created or changed and what each one is.\n"
    "Failures: what failed, the error, and whether it was retried or still open.\n"
    "No raw tool output, no screenshots, no invented facts. At most 300 words.")


def summary_key(upto: int, model_id: str, head_digest: str) -> str:
    """Cache key under the (workspace, owner, project) scope: turns summarized so far, summary model,
    prompt version, plus a digest of those turns so a different chat / edited history never matches."""
    return f"{upto}|{model_id}|{PROMPT_VERSION}|{head_digest}"


async def model_summary(head: list[str], fallback: str, llm: Callable[[str, str], Awaitable[str]], *,
                        model_id: str, workspace_id: str = LOCAL_WORKSPACE_ID,
                        owner_id: str = LOCAL_OWNER_ID, project_id: str = LOCAL_PROJECT_ID,
                        timeout_s: float = DEFAULTS["summary_timeout_s"],
                        store: Optional[KeyValueStore] = None) -> tuple[str, str, int]:
    """Rolling summary of `head` (rendered old turns, oldest first) -> (text, source, new_turns).

    source: 'cache' (0 calls) | 'model' (1 call over previous summary + only the newly pushed-out
    turns) | 'rule' (timeout, error or empty answer: `fallback`, nothing cached, retried next round)."""
    store = store or get_store()
    scope = {"workspace_id": workspace_id, "owner_id": owner_id, "project_id": project_id}
    digests = [_digest("")]
    for t in head:
        digests.append(_digest(digests[-1] + t))
    upto = len(head)
    hit = store.get("summary", summary_key(upto, model_id, digests[upto]), **scope)
    if hit:
        return hit, "cache", 0
    prev, base = "", 0
    for k in range(upto - 1, 0, -1):
        old = store.get("summary", summary_key(k, model_id, digests[k]), **scope)
        if old:
            prev, base = old, k
            break
    new_text = "\n".join(head[base:])
    try:
        text = (await asyncio.wait_for(llm(prev, new_text), timeout_s) or "").strip()
    except Exception:  # noqa: BLE001 - timeout or any model failure falls back
        return fallback, "rule", 0
    if not text:
        return fallback, "rule", 0
    store.put("summary", summary_key(upto, model_id, digests[upto]), text, **scope)
    return text, "model", upto - base
