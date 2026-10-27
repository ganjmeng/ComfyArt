"""#391: storage interface for agent runs. Business code (the loop, the API) only talks to this
interface; the SQLite implementation lives in api/run_store_sqlite.py, so moving to another
database later only replaces that one layer. No SQL and no file paths outside the implementation.

Ownership columns: owner_id (the user) + workspace_id (the project). Locally both default to
"local" / the chat's project; they are used today to scope list/get queries and usage reports.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID

RUN_STATUSES = ("running", "paused", "stopped", "done")


class RunStore(ABC):
    @abstractmethod
    def create_run(self, *, run_id: str, chat_id: str, message_id: str, mode: str, goal: str,
                   owner_id: str = LOCAL_OWNER_ID, workspace_id: str = LOCAL_WORKSPACE_ID,
                   project_id: str = LOCAL_PROJECT_ID,
                   state: Optional[dict] = None) -> dict: ...

    @abstractmethod
    def get_run(self, run_id: str, *, owner_id: Optional[str] = None,
                workspace_id: Optional[str] = None) -> Optional[dict]: ...

    @abstractmethod
    def list_runs(self, *, owner_id: str = LOCAL_OWNER_ID, workspace_id: Optional[str] = None,
                  chat_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]: ...

    @abstractmethod
    def save_checkpoint(self, run_id: str, lease_owner: str, *, status: str, status_detail: str = "",
                        step: int, state: dict, stop: Optional[dict] = None) -> bool:
        """Transactional per-step write. Only the lease holder may write; returns False otherwise."""

    @abstractmethod
    def save_checkpoint_with_usage(self, run_id: str, lease_owner: str, *, status: str, step: int, state: dict,
                                   usage: dict, status_detail: str = "") -> Optional[int]:
        """Atomically write the checkpoint AND insert a usage event (status 'pending') in ONE
        transaction, so a paid call never goes out without its metering row. Returns the usage
        event id, or None when the lease is not ours (nothing written)."""

    @abstractmethod
    def finish_usage_event(self, event_id: int, *, status: str, amount_usd: float = 0.0,
                           artifact_ids: Optional[list] = None, reason: Optional[str] = None) -> None:
        """Move a pending usage event to done|failed once the call returns."""

    @abstractmethod
    def acquire_lease(self, run_id: str, lease_owner: str, ttl_s: float) -> bool:
        """DB lease (lease_owner, lease_expires_at). True when free, expired or already ours."""

    @abstractmethod
    def renew_lease(self, run_id: str, lease_owner: str, ttl_s: float) -> bool: ...

    @abstractmethod
    def release_lease(self, run_id: str, lease_owner: str) -> None: ...

    @abstractmethod
    def mark_interrupted(self) -> int:
        """On server start: `running` runs whose lease has EXPIRED (or that have none) become
        paused(interrupted). Runs still leased by another live instance are left alone."""

    @abstractmethod
    def add_usage_event(self, *, run_id: str, kind: str, reason: str, tool: str = "",
                        amount_usd: float = 0.0, tokens: int = 0, artifact_ids: Optional[list] = None,
                        status: str = "done", call_id: str = "",
                        owner_id: str = LOCAL_OWNER_ID, workspace_id: str = LOCAL_WORKSPACE_ID) -> None:
        """Unified metering record: who (owner/workspace/run), how much, why."""

    @abstractmethod
    def list_usage_events(self, *, run_id: Optional[str] = None, owner_id: Optional[str] = None) -> list[dict]: ...

    @abstractmethod
    def add_run_log(self, *, run_id: str, record: dict, owner_id: str = LOCAL_OWNER_ID,
                    workspace_id: str = LOCAL_WORKSPACE_ID, project_id: str = LOCAL_PROJECT_ID) -> None: ...

    @abstractmethod
    def list_run_logs(self, run_id: str) -> list[dict]: ...


_STORE: Optional[RunStore] = None


def set_run_store(store: Optional[RunStore]) -> None:
    global _STORE
    _STORE = store


def get_run_store() -> Optional[RunStore]:
    return _STORE
