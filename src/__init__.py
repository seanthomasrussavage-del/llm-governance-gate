"""
LLM Governance Gate package.

Core modules:
- router: orchestration + gating
- validator: schema enforcement
- risk_scan: safety scanning
- log_store: append-only audit trail
- schemas: structured contracts
"""

from .router import route_request
from .validator import validate_output
from .risk_scan import scan_for_risk
from .log_store import append_log, read_recent_logs

__all__ = [
    "route_request",
    "validate_output",
    "scan_for_risk",
    "append_log",
    "read_recent_logs",
]
