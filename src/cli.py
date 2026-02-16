"""
cli.py

Command-line entrypoint for LLM Governance Gate.

Run examples:
  python -m src --help
  echo '{"prompt":"hi"}' | python -m src --mode demo
  python -m src --mode demo --input input.json --output out.json

Notes:
- Minimal, dependency-free.
- Reads JSON from stdin or --input.
- Writes JSON to stdout or --output.
- Calls router.route_request() as the single orchestration surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, Optional

from .router import route_request


# ----------------------------
# IO helpers
# ----------------------------

def _read_json(path: Optional[str]) -> Dict[str, Any]:
    if path:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

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


# ----------------------------
# Input normalization (fail-closed)
# ----------------------------

def _normalize_user_input(obj: Any) -> Dict[str, Any]:
    """
    Fail-closed normalization:
    - Must be a dict
    - Must contain "prompt" as a non-empty string (coerce if needed)
    - Optional: "user_id" (str), "metadata" (dict)
    Returns normalized dict or raises ValueError with reason.
    """
    if not isinstance(obj, dict):
        raise ValueError("Input must be a JSON object (dict).")

    # prompt
    if "prompt" not in obj:
        raise ValueError("Missing required field: 'prompt'.")
    prompt = obj.get("prompt", "")
    if prompt is None:
        raise ValueError("Field 'prompt' cannot be null.")
    if not isinstance(prompt, str):
        prompt = str(prompt)

    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Field 'prompt' cannot be empty.")

    # user_id
    user_id = obj.get("user_id", "cli")
    if user_id is None:
        user_id = "cli"
    if not isinstance(user_id, str):
        user_id = str(user_id)

    # metadata
    metadata = obj.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("Field 'metadata' must be a JSON object (dict).")

    return {"prompt": prompt, "user_id": user_id, "metadata": metadata}


# ----------------------------
# CLI
# ----------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="llm-governance-gate",
        description="Governance-first orchestration gate for LLM workflows.",
    )

    p.add_argument("--mode", default="demo", choices=["demo"])
    p.add_argument("--input", help="Path to JSON input file. If omitted, reads JSON from stdin.")
    p.add_argument("--output", help="Path to write JSON output. If omitted, prints to stdout.")
    p.add_argument("--human-approve", action="store_true", help="Simulate human approval gate (local runs).")
    p.add_argument("--trace", action="store_true", help="Include extra trace metadata in returned output.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Read input
    try:
        raw_input = _read_json(args.input)
    except Exception as e:
        _write_json({"status": "error", "reason": f"Failed to read input JSON: {e}"}, args.output)
        return 2

    # Normalize / fail-closed
    try:
        user_input = _normalize_user_input(raw_input)
    except Exception as e:
        _write_json({"status": "blocked", "reason": str(e)}, args.output)
        return 2

    # Single orchestration surface
    try:
        result = route_request(
            user_input=user_input,
            mode=args.mode,
            human_approved=args.human_approve,
            trace=args.trace,
        )
    except Exception as e:
        _write_json({"status": "error", "reason": f"route_request failed: {type(e).__name__}: {e}"}, args.output)
        return 1

    _write_json(result, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
