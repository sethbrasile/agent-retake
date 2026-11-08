import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from ..io import records
from ..model import Messages, Session, content


def updates(path):
    for row in records(path):
        stamp = row.get("timestamp")
        if isinstance(stamp, (int, float)):
            seconds = stamp / 1000 if stamp > 10**11 else stamp
            stamp = datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        yield stamp, row.get("params", {}).get("update", {})


def _from_updates(writer, events):
    role, chunks, started = None, [], None

    def flush():
        if chunks:
            writer.add(role, "text", "".join(chunks), time=started)
            chunks.clear()

    for stamp, ev in events:
        kind = ev.get("sessionUpdate")
        if kind in {"user_message_chunk", "agent_message_chunk"}:
            who = "user" if kind == "user_message_chunk" else "assistant"
            if who != role:
                flush()
            if not chunks:
                started = stamp
            role = who
            chunks.append(content([ev.get("content", {})]))
        elif kind in {"tool_call", "tool_call_update", "turn_completed"}:
            flush()
            call = ev.get("toolCallId")
            if kind == "tool_call":
                writer.add("assistant", "call", ev.get("rawInput", {}), call=call,
                           tool=ev.get("title", "tool"), time=stamp)
            if kind == "tool_call_update" and "rawOutput" in ev:
                writer.add("tool", "result", ev["rawOutput"], call=call, time=stamp)
    flush()


def parse(path: Path) -> Session:
    directory = path.parent
    summary = directory / "summary.json"
    meta = json.loads(summary.read_bytes()) if summary.is_file() else {}
    info = meta.get("info", {})
    session = Session(id=info.get("id", directory.name), harness="grok", cwd=info.get("cwd", ""),
                      started_at=meta.get("created_at"))
    writer = Messages(session)
    chat = directory / "chat_history.jsonl"
    log = directory / "updates.jsonl"
    events = list(updates(log)) if log.is_file() else []
    call_times = {}
    for stamp, ev in events:
        if ev.get("sessionUpdate") == "tool_call":
            call_times.setdefault(ev.get("toolCallId"), stamp)
    if chat.is_file():
        for row in records(chat):
            role = row.get("type")
            ident = row.get("id")
            text = content(row.get("content"))
            if role in {"user", "assistant"}:
                if text:
                    writer.add(role, "text", text, native=ident, time=row.get("timestamp"))
                for call in row.get("tool_calls") or []:
                    cid = call.get("id")
                    writer.add("assistant", "call", call.get("arguments", {}), call=cid,
                               tool=call.get("name", ""), native=["call", cid] if cid else None,
                               time=call_times.get(cid))
            elif role == "tool_result":
                writer.add("tool", "result", text, native=ident, call=row.get("tool_call_id"))
    if not session.messages and events:
        _from_updates(writer, events)
    if not session.messages:
        warnings.warn("Grok session has no visible chat records or ACP updates")
    writer.link()
    return session
