"""Command-line entry point: python -m engine.cli."""

import argparse
import json
import sys

from .compare import compare
from .store import baseline


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
    try:
        args = parser.parse_args(argv)
        if args.command == "baseline":
            result = baseline(args.name, args.url, args.store)
        else:
            result = compare(args.name, args.url, args.store, args.tolerance)
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
