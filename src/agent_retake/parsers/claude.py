from pathlib import Path
import warnings

from ..io import records
from ..model import Messages, Session, content


def _append(path, session, *, namespace="", parent=None):
    writer = Messages(session, namespace)
    agents = {}
    for row in records(path):
        if row.get("type") not in {"user", "assistant"}:
            continue
        if row.get("isMeta") or row.get("isCompactSummary"):
            continue
        payload = row.get("message", {})
        role = payload.get("role", row["type"])
        if role not in ("user", "assistant"):
            continue
        blocks = payload.get("content", "")
        if isinstance(blocks, str):
            blocks = [{"type": "text", "text": blocks}]
        for i, b in enumerate(blocks):
            kind = b.get("type")
            common = dict(native=[row["uuid"], i] if row.get("uuid") else None,
                          time=row.get("timestamp"), parent=parent, canonical=not namespace)
            if kind == "text" and isinstance(b.get("text"), str):
                writer.add(role, "text", b["text"], **common)
            elif kind == "tool_use":
                writer.add("assistant", "call", b.get("input", {}), call=b.get("id"),
                           tool=b.get("name", ""), **common)
            elif kind == "tool_result":
                call = b.get("tool_use_id")
                writer.add("tool", "result", content(b.get("content")), call=call, **common)
                info = row.get("toolUseResult")
                if isinstance(info, dict) and info.get("agentId"):
                    agents[str(info["agentId"])] = call
    writer.link()
    return {agent: writer.calls.get(call) for agent, call in agents.items()}


def parse(path: Path) -> Session:
    head = next((r for r in records(path) if r.get("sessionId") and r.get("cwd")), None)
    if not head:
        raise ValueError(f"{path.name}: missing Claude session metadata")
    session = Session(id=head["sessionId"], harness="claude", cwd=head["cwd"],
                      started_at=head.get("timestamp"))
    parents = _append(path, session)
    children = path.parent / path.stem / "subagents"
    for child in sorted(children.rglob("*.jsonl")):
        agent = child.stem.removeprefix("agent-")
        parent = parents.get(agent)
        if not parent:
            warnings.warn(f"Unlinked Claude child session {agent}")
        parents.update(_append(child, session, namespace=agent, parent=parent))
    return session
