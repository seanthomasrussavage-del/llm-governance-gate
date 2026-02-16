"""
validator.py

Responsible for:
- Enforcing required fields
- Ensuring structured schema compliance
- Blocking malformed outputs
"""

from typing import Dict, Any, List
from schemas import ValidationResult


REQUIRED_FIELDS = ["text"]


def validate_output(structured_output: Dict[str, Any]) -> ValidationResult:
    """
    Validates structured LLM output against required fields and structure.
    Returns a ValidationResult dataclass.
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

    # 3️⃣ Type enforcement
    if "text" in structured_output and not isinstance(structured_output["text"], str):
        errors.append("Field 'text' must be a string")

    # 4️⃣ Empty response block
    if "text" in structured_output and structured_output["text"].strip() == "":
        errors.append("Field 'text' cannot be empty")

    # Final result
    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors
    )
