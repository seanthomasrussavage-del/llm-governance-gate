"""
schemas.py

Schema definitions for LLM Governance Gate.

Defines:
- Input schema
- Router output schema
- Risk report schema
- Validation result schema

These are lightweight structural contracts (no external deps).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ----------------------------
# Input Schema
# ----------------------------

@dataclass
class GovernanceInput:
    """
    Raw user request entering the governance gate.
    """
    user_id: str
    prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ----------------------------
# Validation Schema
# ----------------------------

@dataclass
class ValidationResult:
    """
    Output of validator.py
    """
    is_valid: bool
    errors: List[str] = field(default_factory=list)


# ----------------------------
# Risk Scan Schema
# ----------------------------

@dataclass
class RiskReport:
    """
    Output of risk_scan.py
    """
    risk_level: str  # "low", "medium", "high"
    triggered_rules: List[str] = field(default_factory=list)
    requires_human_review: bool = False


# ----------------------------
# Router Output Schema
# ----------------------------

@dataclass
class GovernanceDecision:
    """
    Final router decision after validation + risk scan.
    """
    approved: bool
    reason: str
    risk_level: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
