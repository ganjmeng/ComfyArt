"""#387: pending ask persistence behind a storage interface.

Business code talks to `AskStore` only — no hardcoded paths. Today's backend is one JSON
file (`pending-asks.json` under the ComfyArt system user dir); swapping to SQLite/DB later
is a one-file change.

Records carry `owner_id` + `workspace_id` (+ `project_id`) with local defaults so a later
per-user / per-workspace split needs no data migration. No tenancy or auth today.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Protocol

from ..bot.run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID
from ._common import app_path
from .memory import atomic_write_json

log = logging.getLogger("comfyart.ask_store")

STORE_NAME = "pending-asks.json"


def stamp_ownership(record: dict) -> dict:
    """Stamp SaaS-ready ownership defaults without inventing tenancy."""
    out = dict(record)
    out["owner_id"] = out.get("owner_id") or LOCAL_OWNER_ID
    out["workspace_id"] = out.get("workspace_id") or LOCAL_WORKSPACE_ID
    out["project_id"] = out.get("project_id") or LOCAL_PROJECT_ID
    return out


class AskStore(Protocol):
    def list_all(self) -> list[dict]: ...
    def list_chat(self, chat_id: str) -> list[dict]: ...
    def put(self, record: dict) -> None: ...
    def delete(self, ask_id: str) -> None: ...
    def clear(self) -> None: ...


class JsonAskStore:
    """Atomic JSON file store. Corrupt / unreadable file → empty list + warning (never crash)."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path_override = path

    def _path(self) -> str:
        return self._path_override or app_path(STORE_NAME)

    def _load(self) -> list[dict]:
        path = self._path()
        if not os.path.exists(path):
            return []
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, ValueError) as e:
            log.warning("pending-asks store unreadable at %s: %s — starting empty", path, e)
            return []
        if not isinstance(raw, dict) or not isinstance(raw.get("asks"), list):
            log.warning("pending-asks store corrupt at %s — starting empty", path)
            return []
        out: list[dict] = []
        for a in raw["asks"]:
            if not isinstance(a, dict):
                continue
            if not a.get("id") or not a.get("chat_id") or not isinstance(a.get("spec"), dict):
                continue
            out.append(stamp_ownership(a))
        return out

    def _save(self, asks: list[dict]) -> None:
        atomic_write_json(self._path(), {"asks": [stamp_ownership(a) for a in asks]})

    def list_all(self) -> list[dict]:
        return self._load()

    def list_chat(self, chat_id: str) -> list[dict]:
        return [a for a in self._load() if a.get("chat_id") == chat_id]

    def put(self, record: dict) -> None:
        asks = [a for a in self._load() if a.get("id") != record["id"]]
        rec = stamp_ownership(record)
        if "created_at" not in rec:
            rec["created_at"] = time.time()
        asks.append(rec)
        self._save(asks)

    def delete(self, ask_id: str) -> None:
        asks = [a for a in self._load() if a.get("id") != ask_id]
        self._save(asks)

    def clear(self) -> None:
        self._save([])


_STORE: Optional[AskStore] = None


def get_store() -> AskStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonAskStore()
    return _STORE


def set_store(store: Optional[AskStore]) -> None:
    """Tests inject a temp-path store; pass None to reset to the default file store."""
    global _STORE
    _STORE = store
