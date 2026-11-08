from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Message(Record):
    id: str
    role: Literal["user", "assistant", "tool"]
    kind: Literal["text", "call", "result"]
    text: str
    tool: str = ""
    timestamp: str | None = None
    call_id: str | None = None
    parent_id: str | None = None
    canonical: bool = True


class Session(Record):
    id: str
    harness: Literal["claude", "codex", "pi", "grok"]
    cwd: str = ""
    started_at: str | None = None
    messages: list[Message] = Field(default_factory=list)


class Conversation(Record):
    version: Literal[1] = 1
    sessions: list[Session]


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def time_value(value: str):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid ISO timestamp") from None
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def content(value) -> str:
    """Extract visible text blocks only. Images and hidden reasoning stay out."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(b["text"] for b in value if isinstance(b, dict)
                         and b.get("type") in {"text", "input_text", "output_text"}
                         and isinstance(b.get("text"), str))
    return ""


class Messages:
    """Give copied records the same IDs while preserving true repetitions."""
    def __init__(self, session: Session, namespace=""):
        self.session = session
        self.namespace = namespace
        self.counts = Counter()
        self.calls = {}
        self.emitted = []

    def add(self, role, kind, text, *, native=None, time=None, tool="", call=None,
            parent=None, canonical=True) -> Message:
        if not isinstance(text, str):
            text = encoded(text)
        identity = native
        if identity is None:
            key = encoded([role, kind, text, time, tool, call])
            self.counts[key] += 1
            identity = [key, self.counts[key]]
        key = encoded([self.session.harness, self.session.id, self.namespace, identity])
        msg = Message(id="m_" + digest(key.encode())[:24], role=role, kind=kind,
                      text=text, tool=tool, timestamp=time, call_id=call,
                      parent_id=parent, canonical=canonical)
        self.session.messages.append(msg)
        self.emitted.append(msg)
        if kind == "call" and call:
            self.calls[call] = msg.id
        return msg

    def link(self):
        for msg in self.emitted:
            if msg.kind == "result":
                msg.parent_id = self.calls.get(msg.call_id, msg.parent_id)
