"""
validator.py

Responsible for:
- Enforcing required fields
- Ensuring structured schema compliance
- Blocking malformed outputs

Aligned with schemas.py v1 contract.
"""

from __future__ import annotations

from typing import Dict, Any, List
from .schemas import ValidationResult


# Required top-level keys for structured output
REQUIRED_FIELDS = ["output"]


def validate_output(structured_output: Dict[str, Any]) -> ValidationResult:
    """
    Validates structured LLM output against required fields and structure.

    Expected structure (v1):
    {
        "status": str,
        "output": str | dict | list,
        "meta": dict
    }

    Returns:
        ValidationResult
    """

    errors: List[str] = []

    # 1️⃣ Must be dict
    if not isinstance(structured_output, dict):
        return ValidationResult(
            is_valid=False,
            errors=["Output is not a dictionary"]
        )

    # 2️⃣ Required fields
    for field in REQUIRED_FIELDS:
        if field not in structured_output:
            errors.append(f"Missing required field: {field}")

    # 3️⃣ Backward compatibility guard
    if "text" in structured_output and "output" not in structured_output:
        errors.append("Legacy 'text' field present without 'output'")

    # 4️⃣ Type enforcement
    if "output" in structured_output and structured_output["output"] is None:
        errors.append("Field 'output' cannot be None")

    # 5️⃣ Status sanity (optional but safe)
    if "status" in structured_output and not isinstance(structured_output["status"], str):
        errors.append("Field 'status' must be a string")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors
    )
