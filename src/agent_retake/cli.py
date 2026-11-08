import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .gather import gather
from .io import atomic
from .storyboard import initialize


def parser():
    root = argparse.ArgumentParser(prog="retake", description="Turn saved agent conversations into narrated-video footage.")
    cmds = root.add_subparsers(dest="command", required=True)
    g = cmds.add_parser("gather", help="Collect sessions from files or project directories")
    g.add_argument("inputs", nargs="+", type=Path)
    g.add_argument("--out", type=Path, required=True)
    g.add_argument("--since")
    g.add_argument("--until")
    g.add_argument("--keyword", action="append", default=[])
    sub = cmds.add_parser("storyboard").add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="Start a storyboard with one beat per user turn")
    init.add_argument("sessions", type=Path)
    init.add_argument("--out", type=Path, required=True)
    scan = cmds.add_parser("scan", help="Find sensitive strings or record reviewed decisions")
    scan.add_argument("board", type=Path)
    scan.add_argument("--review", action="store_true")
    return root


def execute(args):
    if args.command == "scan":
        from .scan import review_board, scan_board
        (review_board if args.review else scan_board)(args.board)
        print(args.board)
    elif args.command == "storyboard":
        initialize(args.sessions, args.out)
        print(args.out)
    elif args.command == "gather":
        conv = gather(args.inputs, since=args.since, until=args.until, keywords=args.keyword)
        if not conv.sessions:
            raise ValueError("no sessions gathered")
        atomic(args.out / "sessions.json", conv.model_dump_json(indent=2) + "\n")
        lines = [f"{s.harness} {s.id}: {len(s.messages)} messages" for s in conv.sessions]
        atomic(args.out / "summary.md", "\n".join(lines) + "\n")
        print(args.out / "sessions.json")


def main(argv=None):
    try:
        execute(parser().parse_args(argv))
    except ValidationError as err:
        locations = ["/".join(map(str, x["loc"])) for x in err.errors()]
        print("retake: invalid field(s): " + ", ".join(locations), file=sys.stderr)
        return 2
    except (ValueError, OSError) as err:
        print(f"retake: {err}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
