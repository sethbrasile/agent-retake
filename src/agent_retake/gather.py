import os
import warnings
from pathlib import Path

from .io import records
from .model import Conversation, time_value
from .parsers import claude


def adapter(path):
    if path.name in {"chat_history.jsonl", "updates.jsonl", "summary.json"}:
        from .parsers import grok
        return grok
    for row in records(path):
        if row.get("type") == "session_meta":
            from .parsers import codex
            return codex
        if row.get("type") == "session":
            from .parsers import pi
            return pi
        if "sessionId" in row:
            return claude
    return None


def roots():
    home = Path.home()
    return [home / sub for sub in (".claude/projects", ".codex/sessions",
                                    ".pi/agent/sessions", ".grok/sessions")]


def candidates(path):
    if path.is_file():
        yield path
        return
    # Never descend into repository dependencies or unrelated data trees.
    for base, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and
                   d not in {"node_modules", "subagents", "__pycache__"}]
        for name in sorted(files):
            if name.endswith(".jsonl"):
                yield Path(base) / name


def metadata_matches(path, dirs):
    if path.name in {"chat_history.jsonl", "updates.jsonl"}:
        import json
        meta = path.with_name("summary.json")
        if not meta.exists():
            return False
        cwd = json.loads(meta.read_bytes()).get("info", {}).get("cwd")
        return cwd and Path(cwd).resolve() in dirs
    for row in records(path):
        obj = row.get("payload") if row.get("type") == "session_meta" else row
        if isinstance(obj, dict) and obj.get("cwd"):
            return Path(obj["cwd"]).resolve() in dirs
    return False


def gather(inputs, *, since=None, until=None, keywords=()) -> Conversation:
    paths = [Path(p).expanduser().resolve() for p in inputs]
    if any(not p.exists() for p in paths):
        raise ValueError("input file or directory does not exist")
    direct = {f for p in paths for f in candidates(p)}
    dirs = {p for p in paths if p.is_dir()}
    if dirs:
        for root in roots():
            if root.is_dir() and not any(root == p or root.is_relative_to(p) for p in dirs):
                for f in candidates(root):
                    if metadata_matches(f, dirs):
                        direct.add(f)
    sessions = {}
    ranks = {}
    for f in sorted(direct):
        module = adapter(f)
        if module is None:
            if f in paths:
                raise ValueError(f"{f.name}: unrecognized transcript format")
            continue
        if f.name in {"updates.jsonl", "summary.json"} and f.with_name("chat_history.jsonl") in direct:
            continue
        try:
            s = module.parse(f)
        except (TypeError, AttributeError, KeyError, IndexError) as err:
            raise ValueError(f"{f.name}: invalid transcript record ({type(err).__name__})") from None
        if since or until:
            if not s.started_at:
                continue
            t = time_value(s.started_at)
            if since and t < time_value(since) or until and t > time_value(until):
                continue
        if keywords and not all(any(k.casefold() in m.text.casefold() for m in s.messages) for k in keywords):
            continue
        unique = {}
        for message in s.messages:
            duplicate = unique.get(message.id)
            if duplicate is not None and duplicate != message:
                raise ValueError(f"{f.name}: conflicting records for one message ID")
            unique[message.id] = message
        s.messages = list(unique.values())
        key = (s.harness, s.id)
        rank = (len(s.messages), f.stat().st_size)
        previous = sessions.get(key)
        if previous:
            latest, older = (s, previous) if rank > ranks[key] else (previous, s)
            known = {m.id: m for m in latest.messages}
            for m in older.messages:
                if m.id in known:
                    skip = {"canonical", "timestamp"}
                    if m.model_dump(exclude=skip) != known[m.id].model_dump(exclude=skip):
                        raise ValueError(f"{f.name}: conflicting copies of a message")
                else:
                    known[m.id] = m.model_copy(update={"canonical": False}) if s.harness == "pi" else m
            latest.messages = list(known.values())
            sessions[key] = latest
        else:
            sessions[key] = s
        ranks[key] = max(rank, ranks.get(key, rank))
    if not sessions:
        warnings.warn("No matching sessions. Check the inputs and filters.")
    ordered = sorted(sessions.values(), key=lambda s: (
        time_value(s.started_at).timestamp() if s.started_at else float("inf"), s.harness, s.id))
    return Conversation(sessions=ordered)
