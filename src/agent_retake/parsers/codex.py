from collections import Counter
from pathlib import Path

from ..io import records
from ..model import Messages, Session, content


def _turn(rows, writer):
    # An event mirror can come before or after its authoritative response item.
    mirrors = Counter()
    for row in rows:
        p = row.get("payload", {})
        if row["type"] == "response_item" and p.get("type") == "message":
            mirrors[p.get("role"), content(p.get("content"))] += 1
    for row in rows:
        p = row.get("payload", {})
        kind = p.get("type")
        opts = dict(time=row.get("timestamp"), native=p.get("id"))
        if row["type"] == "event_msg" and kind in {"user_message", "agent_message"}:
            role = "user" if kind == "user_message" else "assistant"
            text = p.get("message", "")
            if mirrors[role, text]:
                mirrors[role, text] -= 1
            elif text:
                writer.add(role, "text", text, **opts)
        elif row["type"] == "response_item":
            if kind == "message" and p.get("role") in {"user", "assistant"}:
                text = content(p.get("content"))
                if text and not text.startswith(("<environment_context>", "# AGENTS.md instructions for ")):
                    writer.add(p["role"], "text", text, **opts)
            elif kind in {"function_call", "custom_tool_call"}:
                writer.add("assistant", "call", p.get("arguments", p.get("input", "")),
                           tool=p.get("name", ""), call=p.get("call_id"), **opts)
            elif kind in {"function_call_output", "custom_tool_call_output"}:
                value = p.get("output", "")
                writer.add("tool", "result", content(value) if isinstance(value, list) else value,
                           call=p.get("call_id"), **opts)


def parse(path: Path) -> Session:
    rows = iter(records(path))
    head = next((r for r in rows if r.get("type") == "session_meta"), None)
    if not head:
        raise ValueError("missing Codex session metadata")
    meta = head["payload"]
    session = Session(id=meta["id"], harness="codex", cwd=meta.get("cwd", ""),
                      started_at=meta.get("timestamp", head.get("timestamp")))
    writer = Messages(session)
    turn, turn_id = [], None
    for row in rows:
        kind = row.get("type")
        payload = row.get("payload", {})
        ident = payload.get("turn_id")
        if ident and turn_id and ident != turn_id or (kind == "event_msg" and payload.get("type") == "task_started"):
            _turn(turn, writer)
            turn.clear()
        if ident:
            turn_id = ident
        if kind in {"response_item", "event_msg"}:
            turn.append(row)
    _turn(turn, writer)
    writer.link()
    return session
