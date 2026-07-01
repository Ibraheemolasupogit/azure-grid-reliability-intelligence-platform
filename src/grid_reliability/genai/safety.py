"""Critical-infrastructure safety checks."""

from __future__ import annotations

from grid_reliability.genai.models import QueryClassification


def safety_status(classification: QueryClassification) -> tuple[bool, str | None]:
    if classification.restricted_action_detected:
        return False, classification.safety_reason_code or "RESTRICTED_OPERATIONAL_CONTROL"
    if classification.unsupported_current_status:
        return False, "UNSUPPORTED_REAL_WORLD_STATUS"
    return True, None
