"""
risk_scan.py

Risk scanning layer for LLM Governance Gate.

Purpose:
- Flag outputs that require human review (not auto-block by default)
- Keep conservative heuristics (review > block)
- Return RiskReport dataclass aligned with schemas.py
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union

from .schemas import RiskReport


def scan_for_risk(structured_output: Dict[str, Any]) -> RiskReport:
    """
    Scan structured output for risk signals.

    Expected structured_output:
    {
        "status": str,
        "output": Any,
        "meta": dict
    }

    Returns:
        RiskReport(requires_human_review, risk_level, triggered_rules)
    """
    # Prefer scanning only the "output" payload (not the whole envelope)
    payload = structured_output.get("output", structured_output)
    text = _flatten_to_text(payload)
    text_norm = _normalize(text)

    triggered: List[str] = []

    # Secrets / credentials
    if _looks_like_secret(text):
        triggered.append("secrets_or_credentials")

    # Malware / intrusion / evasion
    if _matches_any(text_norm, _MALWARE_PATTERNS):
        triggered.append("malware_or_intrusion")

    # Self-harm
    if _matches_any(text_norm, _SELF_HARM_PATTERNS):
        triggered.append("self_harm")

    # Violence / weapons
    if _matches_any(text_norm, _VIOLENCE_PATTERNS):
        triggered.append("violence_or_weapons")

    # Hate / harassment
    if _matches_any(text_norm, _HATE_HARASSMENT_PATTERNS):
        triggered.append("hate_or_harassment")

    # PII / doxxing-like patterns
    if _matches_any(text_norm, _PII_PATTERNS):
        triggered.append("pii_or_doxxing")

    # Risk level heuristic
    risk_level = "low"
    if triggered:
        risk_level = "medium"
    if any(t in triggered for t in ("malware_or_intrusion", "self_harm", "violence_or_weapons")):
        risk_level = "high"
    if "self_harm" in triggered:
        risk_level = "critical"

    requires_review = len(triggered) > 0

    return RiskReport(
        requires_human_review=requires_review,
        risk_level=risk_level,
        triggered_rules=triggered,
    )


# -------------------------
# Helpers
# -------------------------

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _flatten_to_text(obj: Union[str, Dict[str, Any], List[Any], Any]) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        parts: List[str] = []
        for k, v in obj.items():
            parts.append(str(k))
            parts.append(_flatten_to_text(v))
        return " ".join(parts)
    if isinstance(obj, list):
        return " ".join(_flatten_to_text(x) for x in obj)
    return str(obj)


def _matches_any(text_norm: str, patterns: List[re.Pattern]) -> bool:
    return any(p.search(text_norm) for p in patterns)


def _looks_like_secret(text: str) -> bool:
    candidates = [
        r"\bAKIA[0-9A-Z]{16}\b",
        r"\bgh[pousr]_[0-9A-Za-z]{20,}\b",
        r"\bsk-[0-9A-Za-z]{20,}\b",
        r"\beyJ[a-zA-Z0-9_-]+?\.[a-zA-Z0-9_-]+?\.[a-zA-Z0-9_-]+?\b",
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    ]
    return any(re.search(c, text) for c in candidates)


# -------------------------
# Pattern libraries
# -------------------------

_MALWARE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bransomware\b"),
    re.compile(r"\bkeylogger\b"),
    re.compile(r"\bcredential\s*steal\w*\b"),
    re.compile(r"\bexploit\b"),
    re.compile(r"\bzero[-\s]?day\b"),
    re.compile(r"\brev(?:erse)?\s*shell\b"),
    re.compile(r"\bmetasploit\b"),
    re.compile(r"\bmimikatz\b"),
    re.compile(r"\b(phish|phishing)\b"),
    re.compile(r"\bbypass\b.*\b(auth|authentication|2fa|captcha)\b"),
    re.compile(r"\bdenial\s*of\s*service\b|\bddos\b"),
]

_SELF_HARM_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(suicide|kill\s*myself|end\s*my\s*life)\b"),
    re.compile(r"\bself[-\s]?harm\b"),
    re.compile(r"\bcutting\b"),
    re.compile(r"\boverdose\b"),
]

_VIOLENCE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(make|build|assemble)\b.*\b(bomb|explosive)\b"),
    re.compile(r"\bpipe\s*bomb\b"),
    re.compile(r"\bimprovised\s*explosive\b|\bied\b"),
    re.compile(r"\bghost\s*gun\b"),
    re.compile(r"\bhow\s*to\b.*\bkill\b"),
]

_HATE_HARASSMENT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(hate|inferior|subhuman)\b"),
    re.compile(r"\bslur\b"),
]

_PII_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,}\s+(?:st|street|ave|avenue|rd|road|blvd|lane|ln|dr|drive)\b"),
]
