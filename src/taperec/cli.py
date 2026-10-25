"""taperec CLI: inspect and verify cassettes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .cassette import Cassette, TaperecCassetteError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="taperec",
        description="VCR for LLM agent traffic — cassette inspection tools. "
        "Recording/replaying happens in-process via the taperec library or pytest plugin.",
    )
    parser.add_argument("--version", action="version", version=f"taperec {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_show = sub.add_parser("show", help="summarize a cassette")
    p_show.add_argument("cassettes", nargs="+")
    p_show.add_argument("--json", action="store_true", help="dump full cassette JSON")

    p_verify = sub.add_parser("verify", help="validate cassette schema + redaction")
    p_verify.add_argument("cassettes", nargs="+")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "show":
            return cmd_show(args)
        return cmd_verify(args)
    except (TaperecCassetteError, json.JSONDecodeError) as exc:
        print(f"taperec: {exc}", file=sys.stderr)
        return 2


def cmd_show(args) -> int:
    for path in args.cassettes:
        cas = Cassette.load(path)
        if args.json:
            print(json.dumps(json.loads(Path(path).read_text()), indent=2, sort_keys=True))
            continue
        print(f"{path}  ({len(cas.interactions)} interactions)")
        for ix in cas.interactions:
            size = len(ix.resp_body.encode("utf-8", errors="replace"))
            print(f"  {ix.method:<6} {ix.url}  ->  {ix.status}  {size}B")
    return 0


def cmd_verify(args) -> int:
    failed = False
    for path in args.cassettes:
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
            problems = []
            if data.get("version") != 1:
                problems.append("missing/unknown version")
            if not isinstance(data.get("interactions"), list):
                problems.append("missing interactions list")
            lower = raw.lower()
            for header in ("authorization", "x-api-key", '"api-key"'):
                if header in lower:
                    problems.append(f"redaction failure: {header} found in cassette")
            if problems:
                failed = True
                print(f"✗ {path}: {'; '.join(problems)}")
            else:
                print(f"✓ {path}: {len(data['interactions'])} interactions, schema ok, no secrets")
        except (OSError, json.JSONDecodeError) as exc:
            failed = True
            print(f"✗ {path}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
