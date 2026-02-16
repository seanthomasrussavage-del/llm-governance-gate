"""
router.py

Central orchestration layer for LLM Governance Gate.

Responsible for:
- Receiving user input
- Sending request to LLM layer
- Passing output through validation and risk gates
- Logging execution path
- Requiring human approval before final output
"""

from validator import validate_output
from risk_scan import scan_for_risk
from log_store import append_log
from schemas import enforce_schema


class GovernanceRouter:
    def __init__(self, llm_client):
        self.llm = llm_client

    def handle_request(self, user_input: str) -> dict:
        """
        Main orchestration flow.
        """

        # Step 1 — Send to LLM (mocked or injected client)
        raw_output = self.llm.generate(user_input)

        # Step 2 — Enforce structured schema
        structured_output = enforce_schema(raw_output)

        # Step 3 — Validate policy and structure
        validation_result = validate_output(structured_output)

        if not validation_result["valid"]:
            append_log("VALIDATION_FAILED", validation_result)
            return {
                "status": "blocked",
                "reason": validation_result["reason"]
            }

        # Step 4 — Risk scanning
        risk_flags = scan_for_risk(structured_output)

        if risk_flags:
            append_log("RISK_FLAGGED", risk_flags)
            return {
                "status": "review_required",
                "flags": risk_flags,
                "output": structured_output
            }

        # Step 5 — Log success path
        append_log("APPROVED_FOR_REVIEW", structured_output)

        return {
            "status": "pending_human_approval",
            "output": structured_output
        }
