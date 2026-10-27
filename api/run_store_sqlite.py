"""#391: SQLite implementation of bot.run_store.RunStore (the only place with agent-run SQL)."""
from __future__ import annotations

import json
import time
from typing import Optional

from sqlalchemy import Float, Index, Integer, String, Text, or_, select, update
from sqlalchemy.orm import Mapped, mapped_column

from ..bot.run_budget import LOCAL_OWNER_ID, LOCAL_PROJECT_ID, LOCAL_WORKSPACE_ID
from ..bot.run_store import RunStore
from . import db


class AgentRun(db.Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_owner", "owner_id", "workspace_id", "status"),
                      Index("ix_agent_runs_chat", "chat_id"))

    id:               Mapped[str] = mapped_column(String, primary_key=True)
    owner_id:         Mapped[str] = mapped_column(String, default=LOCAL_OWNER_ID)
    workspace_id:     Mapped[str] = mapped_column(String, default=LOCAL_WORKSPACE_ID)
    project_id:       Mapped[str] = mapped_column(String, default=LOCAL_PROJECT_ID)
    chat_id:          Mapped[str] = mapped_column(String)
    message_id:       Mapped[str] = mapped_column(String, default="")
    status:           Mapped[str] = mapped_column(String, default="running")
    status_detail:    Mapped[str] = mapped_column(String, default="")
    mode:             Mapped[str] = mapped_column(String, default="interactive")
    goal:             Mapped[str] = mapped_column(Text, default="")
    step:             Mapped[int] = mapped_column(Integer, default=0)
    state:            Mapped[str] = mapped_column(Text, default="{}")   # messages_compact, artifacts, plan, budget, tracker, paid
    stop_reason:      Mapped[str] = mapped_column(String, default="")
    stop:             Mapped[str] = mapped_column(Text, default="")
    lease_owner:      Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lease_expires_at: Mapped[float] = mapped_column(Float, default=0.0)
    created_at:       Mapped[float] = mapped_column(Float)
    updated_at:       Mapped[float] = mapped_column(Float)


class AgentUsageEvent(db.Base):
    __tablename__ = "agent_usage_events"
    __table_args__ = (Index("ix_agent_usage_run", "run_id"), Index("ix_agent_usage_owner", "owner_id", "workspace_id"),
                      {"sqlite_autoincrement": True})

    seq:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:       Mapped[str] = mapped_column(String)
    owner_id:     Mapped[str] = mapped_column(String, default=LOCAL_OWNER_ID)
    workspace_id: Mapped[str] = mapped_column(String, default=LOCAL_WORKSPACE_ID)
    kind:         Mapped[str] = mapped_column(String)        # paid_call | llm_tokens
    tool:         Mapped[str] = mapped_column(String, default="")
    amount_usd:   Mapped[float] = mapped_column(Float, default=0.0)
    tokens:       Mapped[int] = mapped_column(Integer, default=0)
    reason:       Mapped[str] = mapped_column(Text, default="")
    artifact_ids: Mapped[str] = mapped_column(Text, default="[]")
    created_at:   Mapped[float] = mapped_column(Float)


class AgentRunLog(db.Base):
    __tablename__ = "agent_run_logs"
    __table_args__ = (Index("ix_agent_run_logs_run", "run_id"), {"sqlite_autoincrement": True})

    seq:          Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id:       Mapped[str] = mapped_column(String)
    owner_id:     Mapped[str] = mapped_column(String, default=LOCAL_OWNER_ID)
    workspace_id: Mapped[str] = mapped_column(String, default=LOCAL_WORKSPACE_ID)
    project_id:   Mapped[str] = mapped_column(String, default=LOCAL_PROJECT_ID)
    record:       Mapped[str] = mapped_column(Text)
    created_at:   Mapped[float] = mapped_column(Float)


def _row(r: AgentRun) -> dict:
    return {"id": r.id, "owner_id": r.owner_id, "workspace_id": r.workspace_id, "project_id": r.project_id, "chat_id": r.chat_id,
            "message_id": r.message_id, "status": r.status, "status_detail": r.status_detail,
            "mode": r.mode, "goal": r.goal, "step": r.step, "state": json.loads(r.state or "{}"),
            "stop_reason": r.stop_reason, "stop": json.loads(r.stop) if r.stop else None,
            "lease_owner": r.lease_owner, "lease_expires_at": r.lease_expires_at,
            "created_at": r.created_at, "updated_at": r.updated_at}


class SqliteRunStore(RunStore):
    def __init__(self, clock=time.time) -> None:
        self._clock = clock
        # create_all is idempotent; the engine may exist already (created before this module loaded)
        db.Base.metadata.create_all(db._engine(), tables=[AgentRun.__table__, AgentUsageEvent.__table__,
                                                           AgentRunLog.__table__])

    def create_run(self, *, run_id, chat_id, message_id, mode, goal, owner_id=LOCAL_OWNER_ID,
                   workspace_id=LOCAL_WORKSPACE_ID, project_id=LOCAL_PROJECT_ID, state=None):
        now = self._clock()
        with db.session() as s, s.begin():
            s.add(AgentRun(id=run_id, owner_id=owner_id, workspace_id=workspace_id, project_id=project_id, chat_id=chat_id,
                           message_id=message_id, status="running", mode=mode, goal=goal, step=0,
                           state=json.dumps(state or {}), created_at=now, updated_at=now))
        return self.get_run(run_id)

    def get_run(self, run_id, *, owner_id=None, workspace_id=None):
        with db.session() as s:
            r = s.get(AgentRun, run_id)
            if r is None or (owner_id and r.owner_id != owner_id) or (workspace_id and r.workspace_id != workspace_id):
                return None
            return _row(r)

    def list_runs(self, *, owner_id=LOCAL_OWNER_ID, workspace_id=None, chat_id=None, status=None):
        q = select(AgentRun).where(AgentRun.owner_id == owner_id)
        if workspace_id:
            q = q.where(AgentRun.workspace_id == workspace_id)
        if chat_id:
            q = q.where(AgentRun.chat_id == chat_id)
        if status:
            q = q.where(AgentRun.status == status)
        with db.session() as s:
            return [_row(r) for r in s.scalars(q.order_by(AgentRun.updated_at))]

    def save_checkpoint(self, run_id, lease_owner, *, status, status_detail="", step, state, stop=None):
        now = self._clock()
        values = {"status": status, "status_detail": status_detail, "step": step,
                  "state": json.dumps(state, ensure_ascii=False, default=str), "updated_at": now}
        if stop is not None:
            values["stop"] = json.dumps(stop, ensure_ascii=False)
            values["stop_reason"] = stop.get("code", "")
        with db.session() as s, s.begin():
            res = s.execute(update(AgentRun).where(AgentRun.id == run_id, AgentRun.lease_owner == lease_owner)
                            .values(**values))
            return res.rowcount == 1

    def acquire_lease(self, run_id, lease_owner, ttl_s):
        now = self._clock()
        with db.session() as s, s.begin():
            res = s.execute(update(AgentRun).where(
                AgentRun.id == run_id,
                or_(AgentRun.lease_owner.is_(None), AgentRun.lease_expires_at < now,
                    AgentRun.lease_owner == lease_owner))
                .values(lease_owner=lease_owner, lease_expires_at=now + ttl_s))
            return res.rowcount == 1

    def renew_lease(self, run_id, lease_owner, ttl_s):
        now = self._clock()
        with db.session() as s, s.begin():
            res = s.execute(update(AgentRun).where(AgentRun.id == run_id, AgentRun.lease_owner == lease_owner)
                            .values(lease_expires_at=now + ttl_s))
            return res.rowcount == 1

    def release_lease(self, run_id, lease_owner):
        with db.session() as s, s.begin():
            s.execute(update(AgentRun).where(AgentRun.id == run_id, AgentRun.lease_owner == lease_owner)
                      .values(lease_owner=None, lease_expires_at=0.0))

    def mark_interrupted(self):
        with db.session() as s, s.begin():
            res = s.execute(update(AgentRun).where(AgentRun.status == "running").values(
                status="paused", status_detail="interrupted", lease_owner=None, lease_expires_at=0.0,
                updated_at=self._clock()))
            return res.rowcount or 0

    def add_usage_event(self, *, run_id, kind, reason, tool="", amount_usd=0.0, tokens=0, artifact_ids=None,
                        owner_id=LOCAL_OWNER_ID, workspace_id=LOCAL_WORKSPACE_ID):
        with db.session() as s, s.begin():
            s.add(AgentUsageEvent(run_id=run_id, owner_id=owner_id, workspace_id=workspace_id, kind=kind,
                                  tool=tool, amount_usd=float(amount_usd), tokens=int(tokens), reason=reason,
                                  artifact_ids=json.dumps(list(artifact_ids or [])), created_at=self._clock()))

    def list_usage_events(self, *, run_id=None, owner_id=None):
        q = select(AgentUsageEvent)
        if run_id:
            q = q.where(AgentUsageEvent.run_id == run_id)
        if owner_id:
            q = q.where(AgentUsageEvent.owner_id == owner_id)
        with db.session() as s:
            return [{"run_id": e.run_id, "owner_id": e.owner_id, "workspace_id": e.workspace_id, "kind": e.kind,
                     "tool": e.tool, "amount_usd": e.amount_usd, "tokens": e.tokens, "reason": e.reason,
                     "artifact_ids": json.loads(e.artifact_ids or "[]"), "created_at": e.created_at}
                    for e in s.scalars(q.order_by(AgentUsageEvent.seq))]

    def add_run_log(self, *, run_id, record, owner_id=LOCAL_OWNER_ID, workspace_id=LOCAL_WORKSPACE_ID,
                    project_id=LOCAL_PROJECT_ID):
        with db.session() as s, s.begin():
            s.add(AgentRunLog(run_id=run_id, owner_id=owner_id, workspace_id=workspace_id, project_id=project_id,
                              record=json.dumps(record, ensure_ascii=False, default=str), created_at=self._clock()))

    def list_run_logs(self, run_id):
        with db.session() as s:
            return [json.loads(r.record) for r in s.scalars(
                select(AgentRunLog).where(AgentRunLog.run_id == run_id).order_by(AgentRunLog.seq))]
