import json
import time
import uuid
from typing import Optional

from sqlalchemy import delete, select, update

from . import db
from .db import Chat, Message

_CHAT_FIELDS = ("id", "user", "project", "title", "provider", "resume_token", "run_mode", "pinned", "archived", "created_at", "updated_at")
_MESSAGE_FIELDS = ("id", "chat_id", "parent_id", "role", "blocks", "status", "resume_token_after", "usage", "created_at")
_JSON_FIELDS = ("blocks", "usage")


def _chat(row: Chat) -> dict:
    return {k: getattr(row, k) for k in _CHAT_FIELDS}


def _message(row: Message) -> dict:
    message = {k: getattr(row, k) for k in _MESSAGE_FIELDS}
    message["blocks"] = json.loads(message["blocks"])
    message["usage"] = json.loads(message["usage"]) if message["usage"] else None
    return message


def _column(key: str, value):
    return json.dumps(value, ensure_ascii=False) if key in _JSON_FIELDS and value is not None else value


def abort_unfinished() -> None:
    with db.session() as s:
        s.execute(update(Message).where(Message.status.in_(("streaming", "queued"))).values(status="aborted"))
        s.commit()


def list_chats(user: str, project: str, *, include_archived: bool = False) -> list[dict]:
    query = select(Chat).where(Chat.user == user, Chat.project == project)
    if not include_archived:
        query = query.where(Chat.archived.is_(False))
    with db.session() as s:
        return [_chat(r) for r in s.scalars(query.order_by(Chat.pinned.desc(), Chat.updated_at.desc()))]


def get_chat(chat_id: str) -> Optional[dict]:
    with db.session() as s:
        row = s.get(Chat, chat_id)
        return _chat(row) if row else None


def create_chat(*, user: str, project: str, provider: str, title: str = "", run_mode: str = "auto") -> dict:
    now = time.time()
    row = Chat(id=uuid.uuid4().hex, user=user, project=project, title=title, provider=provider, resume_token=None,
               run_mode=run_mode, pinned=False, archived=False, created_at=now, updated_at=now)
    with db.session() as s:
        s.add(row)
        s.commit()
        return _chat(row)


def update_chat(chat_id: str, **fields) -> Optional[dict]:
    with db.session() as s:
        row = s.get(Chat, chat_id)
        if row is None:
            return None
        for k, v in fields.items():
            if v is not None:
                setattr(row, k, v)
        row.updated_at = time.time()
        s.commit()
        return _chat(row)


def delete_chat(chat_id: str) -> bool:
    with db.session() as s:
        gone = s.execute(delete(Chat).where(Chat.id == chat_id)).rowcount > 0
        s.commit()
        return gone


def branch_chat(chat_id: str, message_id: str) -> Optional[dict]:
    with db.session() as s:
        source = s.get(Chat, chat_id)
        rows = list(s.scalars(select(Message).where(Message.chat_id == chat_id).order_by(Message.seq)))
        cut = next((i for i, m in enumerate(rows) if m.id == message_id), None)
        if source is None or cut is None:
            return None
        kept = rows[:cut + 1]
        now = time.time()
        branch = Chat(**{**_chat(source), "id": uuid.uuid4().hex, "pinned": False, "archived": False, "created_at": now, "updated_at": now,
                         "resume_token": next((m.resume_token_after for m in reversed(kept) if m.resume_token_after), None)})
        s.add(branch)
        id_map: dict[str, str] = {}
        for m in kept:
            new_id = uuid.uuid4().hex
            s.add(Message(id=new_id, chat_id=branch.id, parent_id=id_map.get(m.parent_id or ""), role=m.role, blocks=m.blocks,
                          status=m.status, resume_token_after=m.resume_token_after, usage=m.usage, created_at=m.created_at))
            id_map[m.id] = new_id
        s.commit()
        return _chat(branch)


def list_messages(chat_id: str) -> list[dict]:
    with db.session() as s:
        return [_message(r) for r in s.scalars(select(Message).where(Message.chat_id == chat_id).order_by(Message.seq))]


def create_message(*, chat_id: str, role: str, blocks: list[dict], status: str = "done",
                   parent_id: Optional[str] = None) -> dict:
    now = time.time()
    row = Message(id=uuid.uuid4().hex, chat_id=chat_id, parent_id=parent_id, role=role, blocks=_column("blocks", blocks),
                  status=status, resume_token_after=None, usage=None, created_at=now)
    with db.session() as s:
        s.add(row)
        s.execute(update(Chat).where(Chat.id == chat_id).values(updated_at=now))
        s.commit()
        return _message(row)


def update_message(chat_id: str, message_id: str, **fields) -> Optional[dict]:
    with db.session() as s:
        row = s.scalars(select(Message).where(Message.id == message_id, Message.chat_id == chat_id)).first()
        if row is None:
            return None
        for k, v in fields.items():
            if v is not None:
                setattr(row, k, _column(k, v))
        s.commit()
        return _message(row)


def compare_message_blocks(chat_id: str, message_id: str, expected: list[dict], blocks: list[dict]) -> bool:
    """#1002 (Refs #911): atomically persist a staged paid reservation, or fail closed.

    No other caller's message blocks may be overwritten between read and submit.
    This is additive; existing message/skill behavior is unchanged.
    """
    with db.session() as s:
        result = s.execute(update(Message).where(
            Message.id == message_id, Message.chat_id == chat_id,
            Message.blocks == _column("blocks", expected),
        ).values(blocks=_column("blocks", blocks)))
        s.commit()
        return result.rowcount == 1
