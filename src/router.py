"""
router.py

Central orchestration layer for LLM Governance Gate.

Deterministic Flow (no bypass):
1) Receive input + create request_id
2) Call LLM client (contained)
3) Enforce minimal output structure
4) Validate structure/policy (validator)
5) Risk scan (risk_scan)
6) Append-only log (log_store) for every branch
7) Return a governance decision (schemas)
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import uuid

# Package-safe imports (src as package)
from .validator import validate_output
from .risk_scan import scan_for_risk
from .log_store import append_log
from .schemas import GovernanceInput, GovernanceDecision, ValidationResult, RiskReport


def _enforce_basic_schema(raw_output: Any) -> Dict[str, Any]:
    """
    Minimal schema enforcement. Keeps router independent of external libs.

    Contract:
    - Always returns a dict
    - Must include "text" (string)
    """
    if raw_output is None:
        return {"text": ""}

    if isinstance(raw_output, dict):
        text_val = raw_output.get("text", "")
        # preserve original keys, but guarantee text is a string
        return {**raw_output, "text": str(text_val)}

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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main orchestration flow.
        Returns a JSON-serializable dict for easy integration.
        """
        request_id = str(uuid.uuid4())
        meta = metadata or {}

        request = GovernanceInput(user_id=user_id, prompt=user_input, metadata=meta)

        # --- Log: request received
        append_log(
            "REQUEST_RECEIVED",
            {"request_id": request_id, "user_id": request.user_id, "metadata": request.metadata},
        )

        # --- Step 1: LLM call (contained)
        try:
            raw_output = self.llm.generate(request.prompt)
            append_log(
                "LLM_OUTPUT_RECEIVED",
                {"request_id": request_id, "raw_type": type(raw_output).__name__},
            )
        except Exception as e:
            append_log(
                "LLM_CALL_FAILED",
                {"request_id": request_id, "error_type": type(e).__name__, "error": str(e)},
            )
            decision = GovernanceDecision(
                approved=False,
                reason="llm_call_failed",
                metadata={"request_id": request_id, "user_id": request.user_id},
            )
            return {**decision.__dict__, "request_id": request_id, "output": {"text": ""}}

        # --- Step 2: Basic schema enforcement
        structured_output = _enforce_basic_schema(raw_output)

        # --- Step 3: Validate policy/structure
        try:
            validation: ValidationResult = validate_output(structured_output)
        except Exception as e:
            append_log(
                "VALIDATION_EXCEPTION",
                {"request_id": request_id, "error_type": type(e).__name__, "error": str(e)},
            )
            decision = GovernanceDecision(
                approved=False,
                reason="validation_exception",
                metadata={"request_id": request_id, "user_id": request.user_id},
            )
            return {**decision.__dict__, "request_id": request_id, "output": structured_output}

        if not validation.is_valid:
            append_log(
                "VALIDATION_FAILED",
                {"request_id": request_id, "errors": validation.errors},
            )
            decision = GovernanceDecision(
                approved=False,
                reason="validation_failed",
                validation_errors=validation.errors,
                metadata={"request_id": request_id, "user_id": request.user_id},
            )
            return {**decision.__dict__, "request_id": request_id, "output": structured_output}

        # --- Step 4: Risk scan
        try:
            risk: RiskReport = scan_for_risk(structured_output)
        except Exception as e:
            append_log(
                "RISK_SCAN_EXCEPTION",
                {"request_id": request_id, "error_type": type(e).__name__, "error": str(e)},
            )
            decision = GovernanceDecision(
                approved=False,
                reason="risk_scan_exception",
                metadata={"request_id": request_id, "user_id": request.user_id},
            )
            return {**decision.__dict__, "request_id": request_id, "output": structured_output}

        if risk.requires_human_review:
            append_log(
                "RISK_FLAGGED",
                {
                    "request_id": request_id,
                    "risk_level": risk.risk_level,
                    "rules": risk.triggered_rules,
                },
            )
            decision = GovernanceDecision(
                approved=False,
                reason="risk_flagged_review_required",
                risk_level=risk.risk_level,
                metadata={
                    "request_id": request_id,
                    "user_id": request.user_id,
                    "triggered_rules": risk.triggered_rules,
                },
            )
            return {**decision.__dict__, "request_id": request_id, "output": structured_output}

        # --- Step 5: Default stance = pending human approval
        append_log(
            "APPROVED_FOR_REVIEW",
            {"request_id": request_id, "risk_level": risk.risk_level},
        )
        decision = GovernanceDecision(
            approved=False,
            reason="pending_human_approval",
            risk_level=risk.risk_level,
            metadata={"request_id": request_id, "user_id": request.user_id},
        )
        return {**decision.__dict__, "request_id": request_id, "output": structured_output}
