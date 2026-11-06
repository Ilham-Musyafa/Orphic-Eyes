"""Command-line entry point: python -m engine.cli."""

import argparse
import json
import sys

from .compare import compare
from .store import accept, approve, baseline, ignore_add, ignore_list, ignore_remove


def _region(text):
    from .regions import _rectangle
    try:
        return _rectangle(tuple(int(part) for part in text.split(",")))
    except Exception:
        raise ValueError("region must be x,y,w,h with x,y >= 0 and w,h > 0") from None


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    """Print one JSON result (or one-line error) and return the exit code."""
    parser = _Parser(description="Capture local visual-regression baselines and diffs")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("baseline", "compare"):
        sub = commands.add_parser(command)
        sub.add_argument("name")
        sub.add_argument("url")
        sub.add_argument("--store", required=True)
        if command == "compare":
            sub.add_argument("--tolerance", type=int, default=0)
            sub.add_argument("--expect", type=_region, action="append", default=[])
            sub.add_argument("--requests", help="Local JSON file containing up to 8 Point & Tell intents")
    ignore = commands.add_parser("ignore")
    actions = ignore.add_subparsers(dest="action", required=True)
    for action in ("add", "list", "remove"):
        sub = actions.add_parser(action)
        sub.add_argument("name")
        sub.add_argument("--store", required=True)
        if action == "add":
            sub.add_argument("--region", type=_region, required=True)
            sub.add_argument("--label")
        elif action == "remove":
            sub.add_argument("--label", required=True)
    for command in ("approve", "accept"):
        sub = commands.add_parser(command)
        sub.add_argument("name")
        sub.add_argument("--store", required=True)
        if command == "approve":
            selection = sub.add_mutually_exclusive_group(required=True)
            selection.add_argument("--box", type=int, action="append")
            selection.add_argument("--all", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.command == "baseline":
            result = baseline(args.name, args.url, args.store)
        elif args.command == "compare":
            requests = None
            if args.requests is not None:
                from .requests import validate_requests
                with open(args.requests, encoding="utf-8") as handle:
                    requests = validate_requests(json.load(handle))
            result = compare(args.name, args.url, args.store, args.tolerance, args.expect,
                             requests=requests)
        elif args.command == "ignore":
            if args.action == "add":
                result = ignore_add(args.name, args.store, args.region, args.label)
            elif args.action == "list":
                result = ignore_list(args.name, args.store)
            else:
                result = ignore_remove(args.name, args.store, args.label)
        elif args.command == "approve":
            result = approve(args.name, args.store, args.box, args.all)
        else:
            result = accept(args.name, args.store)
        if result["status"] == "error":
            print("error: " + " ".join(str(result["error"]).splitlines()), file=sys.stderr)
            return 3
        print(json.dumps(result, ensure_ascii=True))
        return {"pass": 0, "check": 1, "fail": 2}[result["status"]]
    except Exception as exc:
        print("error: " + " ".join(str(exc).splitlines()), file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
