"""
schemas.py

Schema layer for LLM Governance Gate.

Purpose:
- Provide minimal typed containers used by router + gates
- Offer small, dependency-free coercion helpers for raw LLM output

This is intentionally minimal v1:
structure first, policy later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ----------------------------
# Core dataclasses (router API)
# ----------------------------

@dataclass
class GovernanceInput:
    user_id: str
    prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """
    Returned by validator.validate_output(...)
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class RiskReport:
    """
    Returned by risk_scan.scan_for_risk(...)
    """
    requires_human_review: bool
    risk_level: str = "low"  # low | medium | high | critical
    triggered_rules: List[str] = field(default_factory=list)


@dataclass
class GovernanceDecision:
    """
    Router return envelope (decision only; output is attached by router).
    """
    approved: bool
    reason: str
    risk_level: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ----------------------------
# Minimal coercion helper (v1)
# ----------------------------

REQUIRED_TOP_LEVEL_KEYS = ("status", "output")


def enforce_schema(raw_output: Any) -> Dict[str, Any]:
    """
    Coerce raw LLM output into a structured dict with required keys.

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

        if "status" not in structured:
            structured["status"] = "schema_coerced"

        if "output" not in structured:
            # try common alternatives, otherwise embed whole dict
            if "response" in structured:
                structured["output"] = structured.pop("response")
            elif "result" in structured:
                structured["output"] = structured.pop("result")
            elif "text" in structured:
                structured["output"] = structured.get("text", "")
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
