"""
cli.py

Command-line entrypoint for LLM Governance Gate.

Run examples:
  python -m src --help
  echo '{"prompt":"hi"}' | python -m src --mode demo
  python -m src --mode demo --input input.json --output out.json

Notes:
- This CLI is intentionally minimal and dependency-free.
- It supports stdin or a JSON file as input.
- It calls router.route_request() as the single orchestration surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from .router import route_request


def _read_json(path: Optional[str]) -> Dict[str, Any]:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # stdin fallback
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def _write_json(data: Any, path: Optional[str]) -> None:
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return

    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm-governance-gate",
        description="Governance-first orchestration gate for LLM workflows.",
    )

    p.add_argument(
        "--mode",
        default="demo",
        choices=["demo"],
        help="Routing mode (demo for now; extend later).",
    )

    p.add_argument(
        "--input",
        help="Path to JSON input file. If omitted, reads JSON from stdin.",
    )

    p.add_argument(
        "--output",
        help="Path to write JSON output. If omitted, prints to stdout.",
    )

    p.add_argument(
        "--human-approve",
        action="store_true",
        help="Simulate human approval gate as approved (for local runs).",
    )

    p.add_argument(
        "--trace",
        action="store_true",
        help="Include extra trace metadata in the returned output.",
    )

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        user_input = _read_json(args.input)
    except Exception as e:
        _write_json({"status": "error", "reason": f"Failed to read input JSON: {e}"}, args.output)
        return 2

    # Minimal contract: router expects dict
    if not isinstance(user_input, dict):
        _write_json({"status": "blocked", "reason": "Input must be a JSON object (dict)."}, args.output)
        return 2

    # Pass through the router as the ONLY entrypoint.
    result = route_request(
        user_input=user_input,
        mode=args.mode,
        human_approved=args.human_approve,
        trace=args.trace,
    )

    _write_json(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
