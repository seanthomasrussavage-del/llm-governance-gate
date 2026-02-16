"""
risk_scan.py

Lightweight risk-scanning layer for LLM Governance Gate.

Purpose:
- Identify outputs that require human review before release
- Flag common unsafe patterns (secrets, malware-ish instructions, self-harm, violence, hate/harassment)
- Keep this intentionally simple + conservative (review > block)

Returns:
- [] if no issues
- List[dict] of flags if review is required
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Union


def scan_for_risk(output: Union[str, Dict[str, Any], List[Any]]) -> List[Dict[str, Any]]:
    """
    Scan structured output for risk signals.
    Returns a list of flags (empty list means "no risk detected").
    """
    text = _flatten_to_text(output)
    text_norm = _normalize(text)

    flags: List[Dict[str, Any]] = []

    # --- High-signal categories (review-required) ---
    # Secrets / credentials
    if _looks_like_secret(text):
        flags.append(_flag("secrets", "Possible credential/secret detected (keys, tokens, passwords)."))

    # Malware / hacking / intrusion
    if _matches_any(text_norm, _MALWARE_PATTERNS):
        flags.append(_flag("malware_or_intrusion", "Contains patterns associated with malware, intrusion, or evasion."))

    # Self-harm
    if _matches_any(text_norm, _SELF_HARM_PATTERNS):
        flags.append(_flag("self_harm", "Contains self-harm ideation or instructions."))

    # Violence / weapons (instructional)
    if _matches_any(text_norm, _VIOLENCE_PATTERNS):
        flags.append(_flag("violence_or_weapons", "Contains violence/weapon instruction signals."))

    # Hate / harassment
    if _matches_any(text_norm, _HATE_HARASSMENT_PATTERNS):
        flags.append(_flag("hate_or_harassment", "Contains hate/harassment signals."))

    # PII / doxxing-like content
    if _matches_any(text_norm, _PII_PATTERNS):
        flags.append(_flag("pii_or_doxxing", "Contains personal data patterns (emails/phones/SSNs/addresses)."))

    # NOTE: We intentionally do NOT block here.
    # Router will interpret any flags as "review_required".

    return flags


# -------------------------
# Helpers
# -------------------------

def _flag(code: str, message: str) -> Dict[str, Any]:
    return {"code": code, "message": message}


def _normalize(text: str) -> str:
    # Lowercase, collapse whitespace for more robust matching
    return re.sub(r"\s+", " ", text).strip().lower()


def _flatten_to_text(obj: Union[str, Dict[str, Any], List[Any]]) -> str:
    """
    Converts nested structured output into a single string for scanning.
    """
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
    """
    Detect common key/token shapes. Conservative: review-required, not proof.
    """
    candidates = [
        # AWS access key id
        r"\bAKIA[0-9A-Z]{16}\b",
        # AWS secret access key (approx length/base64-ish)
        r"\b[0-9A-Za-z/+]{40}\b",
        # GitHub tokens (classic / fine-grained patterns evolve; keep generic)
        r"\bgh[pousr]_[0-9A-Za-z]{20,}\b",
        # OpenAI-style keys (generic)
        r"\bsk-[0-9A-Za-z]{20,}\b",
        # Generic JWT
        r"\beyJ[a-zA-Z0-9_-]+?\.[a-zA-Z0-9_-]+?\.[a-zA-Z0-9_-]+?\b",
        # Private key blocks
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
    re.compile(r"\bimprovised\s*explosive\b|\bIED\b"),
    re.compile(r"\bghost\s*gun\b"),
    re.compile(r"\bhow\s*to\b.*\bkill\b"),
]

_HATE_HARASSMENT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b(kill|hurt)\b.*\b(?:them|him|her)\b"),
    re.compile(r"\b(hate|inferior|subhuman)\b"),
    re.compile(r"\bslur\b"),
]

_PII_PATTERNS: List[re.Pattern] = [
    # Email
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # US phone (very rough)
    re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"),
    # SSN (US)
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    # Street address-ish (very rough; review-only)
    re.compile(r"\b\d{1,6}\s+[A-Za-z0-9.\s]{2,}\s+(?:st|street|ave|avenue|rd|road|blvd|lane|ln|dr|drive)\b"),
]
