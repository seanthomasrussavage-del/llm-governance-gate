"""
validator.py

Validation layer for LLM Governance Gate.

Responsible for:
- Ensuring structured schema compliance
- Enforcing required fields
- Blocking malformed or policy-breaking outputs
"""

REQUIRED_FIELDS = ["status", "output"]


def validate_output(structured_output: dict) -> dict:
    """
    Validates structured LLM output against required fields and structure.
    """

    if not isinstance(structured_output, dict):
        return {
            "valid": False,
            "reason": "Output is not a dictionary."
        }

    for field in REQUIRED_FIELDS:
        if field not in structured_output:
            return {
                "valid": False,
                "reason": f"Missing required field: {field}"
            }

    return {
        "valid": True
    }
