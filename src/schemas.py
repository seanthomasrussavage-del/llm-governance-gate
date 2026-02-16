"""
schemas.py

Schema enforcement layer for LLM Governance Gate.

Purpose:
- Normalize raw LLM output into a predictable dict
- Enforce required fields + safe defaults
- Prevent router/runtime crashes from malformed outputs

This is intentionally minimal v1:
structure first, policy later.
"""

from __future__ import annotations

from typing import Any, Dict


REQUIRED_TOP_LEVEL_KEYS = ("status", "output")


def enforce_schema(raw_output: Any) -> Dict[str, Any]:
    """
    Coerce raw LLM output into a structured dict with required keys.

    Accepts:
    - dict (preferred)
    - str  (wrapped)
    - any  (stringified and wrapped)

    Returns:
    {
      "status": "ok" | "needs_review" | "schema_coerced",
      "output": <content>,
      "meta": { ... optional context ... }
    }
    """
    # 1) If already a dict, normalize keys
    if isinstance(raw_output, dict):
        structured: Dict[str, Any] = dict(raw_output)

        # Ensure required keys exist
        if "status" not in structured:
            structured["status"] = "schema_coerced"
        if "output" not in structured:
            # try common alternatives, otherwise embed whole dict
            if "response" in structured:
                structured["output"] = structured.pop("response")
            elif "result" in structured:
                structured["output"] = structured.pop("result")
            else:
                structured["output"] = structured

        structured.setdefault("meta", {})
        structured["meta"].setdefault("schema_version", "v1")
        return structured

    # 2) If string, wrap it
    if isinstance(raw_output, str):
        return {
            "status": "schema_coerced",
            "output": raw_output.strip(),
            "meta": {"schema_version": "v1", "coerced_from": "str"},
        }

    # 3) Anything else: stringify + wrap
    return {
        "status": "schema_coerced",
        "output": str(raw_output),
        "meta": {"schema_version": "v1", "coerced_from": type(raw_output).__name__},
    }
