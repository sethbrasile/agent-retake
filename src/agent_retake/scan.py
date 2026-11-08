"""Private literal inventory and reproducible evidence of operator review."""
import ipaddress
import json
import re
from pathlib import Path

from .io import atomic
from .model import Conversation, digest, encoded
from .storyboard import Review, Rule, load_board, save_board

VERSION = 1
PATTERNS = {
    "API key": r"\b(?:sk-(?:proj-|ant-)?|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|ASIA)[A-Za-z0-9_-]{12,}",
    "email": r"[\w.+%-]+@(?:[\w-]+\.)+[\w-]+",
    "IPv4": r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])",
    "IPv6": r"(?<![\w:])(?=[a-fA-F0-9:]*:)[a-fA-F0-9:]{2,}(?![\w:])",
    "home path": r"(?:/home/|/Users/)[^/\s\"'\\]+",
    "hostname": r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b",
    "cloud account": r"(?<!\d)\d{12}(?!\d)",
    "hex identifier": r"\b[0-9a-fA-F]{24,}\b",
    "encoded token": r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])",
    "phone": r"(?<!\w)(?:\+\d{1,3}[-. ]?)?(?:\(\d{3}\)|\d{3})[-. ]\d{3}[-. ]\d{4}(?!\d)",
}


def find_hits(strings):
    hits = {}
    for text in strings:
        for kind, pattern in PATTERNS.items():
            for match in re.finditer(pattern, text):
                value = match.group()
                if kind.startswith("IPv"):
                    try:
                        ipaddress.ip_address(value)
                    except ValueError:
                        continue
                hits.setdefault(value, kind)
    return hits


def finding_id(value):
    return "hit_" + digest(value.encode())[:20]


def replacement(value, kind, attempt):
    seed = digest(encoded([value, attempt]).encode())
    n = int(seed[:8], 16)
    tag = seed[:8]
    if kind == "IPv4":
        return f"10.{n >> 16 & 255}.{n >> 8 & 255}.{n & 255}"
    if kind == "IPv6":
        return f"fd00::{seed[:4]}:{seed[4:8]}"
    if kind == "email":
        return f"editor-{tag}@example.invalid"
    if kind == "hostname":
        return f"host-{tag}.invalid"
    if kind == "home path":
        return value.rsplit("/", 1)[0] + "/editor-" + tag
    if kind == "phone":
        return f"+1 202-555-{100 + n % 100:04d}"
    if kind == "cloud account":
        return f"{n:012}"
    if kind == "API key":
        prefix = re.match(r"(?:sk-(?:proj-|ant-)?|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|ASIA)", value).group()
        return prefix + (seed * (1 + len(value) // len(seed)))[:len(value)-len(prefix)]
    return (seed * (1 + len(value) // len(seed)))[:len(value)]


def load_inputs(board, directory):
    bundles = [(directory / name).read_bytes() for name in board.sessions]
    sessions = []
    for raw in bundles:
        sessions.extend(Conversation.model_validate_json(raw).sessions)
    ids = [m.id for s in sessions for m in s.messages]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate message IDs in session inputs; gather overlapping sessions together")
    hashes = [digest(raw) for raw in bundles]
    signature = hashes[0] if len(hashes) == 1 else digest(encoded(hashes).encode())
    return Conversation(sessions=sessions), signature


def visible(board):
    return [board.title, *(b.title for b in board.beats),
            *(h for b in board.beats for shot in b.shots for h in shot.highlight)]


def inventory(board, conv):
    strings = visible(board)
    for s in conv.sessions:
        strings.extend([s.cwd, s.id])
        for m in s.messages:
            strings.extend([m.tool, m.text])
    return find_hits(strings)


def sidecar_values(path, board):
    ref = board.redactions.sidecar
    if not ref:
        return {}
    data = json.loads((path.parent / ref).read_bytes())
    if not isinstance(data, dict) or any(not isinstance(v, str) or finding_id(v) != k for k, v in data.items()):
        raise ValueError("invalid private scan sidecar; rescan")
    return data


def scan_board(path):
    board = load_board(path)
    conv, signature = load_inputs(board, path.parent)
    hits = inventory(board, conv)
    old = sidecar_values(path, board)
    decisions = {}
    for rule in board.redactions.rules:
        value = rule.match or old.get(rule.id)
        if value:
            decisions[value] = rule
            if rule.match or rule.reason not in PATTERNS:
                hits.setdefault(value, "editorial")
    rules = []
    used = set(hits)
    for value, kind in sorted(hits.items()):
        rule = decisions.get(value)
        if rule is None:
            for attempt in range(1000):
                candidate = replacement(value, kind, attempt)
                if candidate not in used and not any(v in candidate for v in hits):
                    break
            else:
                raise ValueError(f"choose a replacement for {finding_id(value)}")
            rule = Rule(replace=candidate, reason=kind)
            used.add(candidate)
        rules.append(Rule(id=finding_id(value), replace=rule.replace, keep=rule.keep, reason=rule.reason))
    data = encoded({finding_id(v): v for v in hits})
    sidecar = (path.parent / board.sessions[0]).parent / ("retake-redactions-" + digest(data.encode())[:20] + ".json")
    atomic(sidecar, data)
    import os
    board.redactions = Review(scan_version=VERSION, sessions_sha256=signature, rules=rules,
                              sidecar=os.path.relpath(sidecar, path.parent), reviewed=False)
    save_board(board, path)


def binding(board, mapping):
    review = board.redactions
    return digest(encoded([review.scan_version, review.sessions_sha256, board.sessions,
                           visible(board), [r.model_dump() for r in review.rules], mapping]).encode())


def validate(path, board, conv, signature, *, require_review):
    review = board.redactions
    if review.scan_version != VERSION or review.sessions_sha256 != signature:
        raise ValueError("missing or stale scan; run retake scan again")
    private = sidecar_values(path, board)
    expected = inventory(board, conv)
    missing = {**dict.fromkeys(private.values()), **expected}
    mapping = {}
    errors = []
    for rule in review.rules:
        value = rule.match or private.get(rule.id)
        if not value or (rule.id and rule.id != finding_id(value)) or value in mapping:
            errors.append(rule.id or "unnamed rule")
            continue
        missing.pop(value, None)
        if not rule.reason.strip() or rule.keep == (rule.replace is not None) or rule.replace == "":
            errors.append(finding_id(value))
        mapping[value] = value if rule.keep else rule.replace
    errors.extend(finding_id(v) for v in missing)
    for value, new in mapping.items():
        if new != value and new and any(key in new for key in mapping):
            errors.append(finding_id(value))
        if new == value and not any(r.keep and (r.match or private.get(r.id)) == value for r in review.rules):
            errors.append(finding_id(value))
    if errors:
        raise ValueError("unresolved or conflicting redaction rules: " + ", ".join(sorted(set(errors))))
    stamp = binding(board, mapping)
    if require_review and (not review.reviewed or stamp != review.review_sha256):
        raise ValueError("redaction review required; inspect rules and run retake scan BOARD --review")
    return mapping, stamp


def review_board(path):
    board = load_board(path)
    conv, signature = load_inputs(board, path.parent)
    _, stamp = validate(path, board, conv, signature, require_review=False)
    board.redactions.review_sha256 = stamp
    board.redactions.reviewed = True
    save_board(board, path)
