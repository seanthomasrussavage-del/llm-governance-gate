"""
log_store.py

Append-only logging for LLM Governance Gate.

Goals:
- Immutable-ish, append-only event trail (JSONL)
- Minimal dependencies
- Safe-by-default redaction for obvious secrets
- Structured events for audit + replay

Writes:
- ./logs/governance_log.jsonl   (newline-delimited JSON)
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List


# ---------- Config ----------

DEFAULT_LOG_DIR = os.getenv("GOV_GATE_LOG_DIR", "logs")
DEFAULT_LOG_FILE = os.getenv("GOV_GATE_LOG_FILE", "governance_log.jsonl")

# If True, redact obvious secrets in payload before writing.
REDACT_SECRETS = os.getenv("GOV_GATE_REDACT_SECRETS", "1") != "0"

# Conservative secret patterns (best-effort, not perfect)
_SECRET_PATTERNS = [
    # key/value-ish secrets
    re.compile(r"(?i)\b(api[_-]?key|secret|token|bearer)\b\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{8,})['\"]?"),
    # GitHub tokens
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    # AWS access key id
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic long base64-ish / token-ish blobs (avoid over-redacting normal prose)
    re.compile(r"\b[A-Za-z0-9\-_]{32,}\b"),
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_log_path(log_dir: str = DEFAULT_LOG_DIR, log_file: str = DEFAULT_LOG_FILE) -> str:
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, log_file)


def _redact_value(value: Any) -> Any:
    """
    Redacts secrets inside strings, and recursively walks dict/list payloads.
    Best-effort: do not assume perfection.
    """
    if not REDACT_SECRETS:
        return value

    if isinstance(value, str):
        # If it looks like a private key block, nuke the whole string.
        if "-----BEGIN" in value and "PRIVATE KEY-----" in value:
            return "[REDACTED_PRIVATE_KEY_BLOCK]"

        redacted = value
        for pat in _SECRET_PATTERNS:
            redacted = pat.sub("[REDACTED]", redacted)
        return redacted

    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_redact_value(v) for v in value]

    return value


@dataclass(frozen=True)
class LogEvent:
    event_id: str
    timestamp_utc: str
    event_type: str
    payload: Dict[str, Any]
    meta: Dict[str, Any]


def append_log(
    event_type: str,
    payload: Any,
    *,
    meta: Optional[Dict[str, Any]] = None,
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
) -> str:
    """
    Append a single event to the JSONL log.

    Returns:
        event_id (str)
    """
    event_id = str(uuid.uuid4())
    log_path = _ensure_log_path(log_dir, log_file)

    safe_payload: Dict[str, Any]
    if isinstance(payload, dict):
        safe_payload = payload
    else:
        safe_payload = {"data": payload}

    event = LogEvent(
        event_id=event_id,
        timestamp_utc=_utc_now_iso(),
        event_type=event_type,
        payload=_redact_value(safe_payload),
        meta=_redact_value(meta or {}),
    )

    line = json.dumps(asdict(event), ensure_ascii=False)

    # Append-only write (durable-ish)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())

    return event_id


def read_recent_logs(
    limit: int = 50,
    *,
    log_dir: str = DEFAULT_LOG_DIR,
    log_file: str = DEFAULT_LOG_FILE,
) -> List[Dict[str, Any]]:
    """
    Convenience reader: returns most recent N events (best effort).
    """
    log_path = os.path.join(log_dir, log_file)
    if not os.path.exists(log_path):
        return []

    # naive tail read (OK for small logs)
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-max(limit, 0):]

    out: List[Dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out
