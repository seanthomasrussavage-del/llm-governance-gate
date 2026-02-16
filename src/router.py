"""
router.py

Central orchestration layer for LLM Governance Gate.

Flow:
1) Receive input
2) Call LLM client
3) Enforce minimal output structure
4) Validate structure/policy (validator)
5) Risk scan (risk_scan)
6) Append-only log (log_store)
7) Return a governance decision (schemas)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from validator import validate_output
from risk_scan import scan_for_risk
from log_store import append_log
from schemas import GovernanceInput, GovernanceDecision, ValidationResult, RiskReport


def _enforce_basic_schema(raw_output: Any) -> Dict[str, Any]:
    """
    Minimal schema enforcement.
    Keeps router independent of external libs.

    Contract:
    - Always returns a dict
    - Must include "text" (string)
    """
    if raw_output is None:
        return {"text": ""}

    if isinstance(raw_output, dict):
        # Ensure "text" key exists
        text_val = raw_output.get("text", "")
        return {**raw_output, "text": str(text_val)}

    # Coerce everything else to text
    return {"text": str(raw_output)}


class GovernanceRouter:
    def __init__(self, llm_client: Any):
        """
        llm_client must implement:
        - generate(prompt: str) -> str | dict
        """
        self.llm = llm_client

    def handle_request(
        self,
        user_input: str,
        *,
        user_id: str = "anonymous",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main orchestration flow.
        Returns a JSON-serializable dict for easy integration.
        """
        meta = metadata or {}
        request = GovernanceInput(user_id=user_id, prompt=user_input, metadata=meta)

        append_log("REQUEST_RECEIVED", {"user_id": request.user_id, "metadata": request.metadata})

        # Step 1 — Send to LLM
        raw_output = self.llm.generate(request.prompt)
        append_log("LLM_OUTPUT_RECEIVED", {"raw_type": type(raw_output).__name__})

        # Step 2 — Enforce basic schema
        structured_output = _enforce_basic_schema(raw_output)

        # Step 3 — Validate policy/structure
        validation: ValidationResult = validate_output(structured_output)

        if not validation.is_valid:
            decision = GovernanceDecision(
                approved=False,
                reason="validation_failed",
                validation_errors=validation.errors,
                metadata={"user_id": request.user_id}
            )
            append_log("VALIDATION_FAILED", {"errors": validation.errors})
            return decision.__dict__ | {"output": structured_output}

        # Step 4 — Risk scan
        risk: RiskReport = scan_for_risk(structured_output)

        if risk.requires_human_review:
            decision = GovernanceDecision(
                approved=False,
                reason="risk_flagged_review_required",
                risk_level=risk.risk_level,
                metadata={
                    "triggered_rules": risk.triggered_rules,
                    "user_id": request.user_id
                }
            )
            append_log("RISK_FLAGGED", {"risk_level": risk.risk_level, "rules": risk.triggered_rules})
            return decision.__dict__ | {"output": structured_output}

        # Step 5 — Approved for human final gate (default stance)
        decision = GovernanceDecision(
            approved=False,
            reason="pending_human_approval",
            risk_level=risk.risk_level,
            metadata={"user_id": request.user_id}
        )
        append_log("APPROVED_FOR_REVIEW", {"risk_level": risk.risk_level})
        return decision.__dict__ | {"output": structured_output}
