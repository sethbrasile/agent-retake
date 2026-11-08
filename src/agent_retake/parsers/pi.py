from pathlib import Path

from ..io import records
from ..model import Messages, Session, content


def canonical_path(rows):
    parents = {r["id"]: r.get("parentId") for r in rows}
    if len(parents) != len(rows):
        raise ValueError("duplicate pi entry ID")
    visited = set()
    canonical = set()
    for i, node in enumerate(reversed(parents)):
        path = set()
        while node is not None and node not in visited:
            if node in path:
                raise ValueError("cycle in pi session")
            if node not in parents:
                raise ValueError("missing pi parent entry")
            path.add(node)
            node = parents[node]
        if i == 0:
            canonical = path
        visited.update(path)
    return canonical


def parse(path: Path) -> Session:
    rows = iter(records(path))
    head = next(rows)
    version = head.get("version", 1)
    if version not in (1, 2, 3):
        raise ValueError("unsupported pi session version")
    session = Session(id=head["id"], harness="pi", cwd=head.get("cwd", ""), started_at=head.get("timestamp"))
    rows = list(rows)
    canonical = canonical_path(rows) if version > 1 else None
    writer = Messages(session)
    for row in rows:
        if row.get("type") != "message":
            continue
        msg = row["message"]
        role = msg.get("role")
        opts = dict(time=row.get("timestamp"), canonical=canonical is None or row["id"] in canonical)
        blocks = msg.get("content", "")
        native = row.get("id")
        if role in ("user", "assistant"):
            if isinstance(blocks, str):
                blocks = [{"type": "text", "text": blocks}]
            for i, b in enumerate(blocks):
                ident = [native, i] if native else None
                if b.get("type") == "text":
                    writer.add(role, "text", b["text"], native=ident, **opts)
                elif b.get("type") == "toolCall":
                    writer.add("assistant", "call", b.get("arguments", {}), native=ident,
                               tool=b.get("name", ""), call=b.get("id"), **opts)
        elif role == "toolResult":
            writer.add("tool", "result", content(blocks), tool=msg.get("toolName", ""),
                       native=native, call=msg.get("toolCallId"), **opts)
    writer.link()
    return session
