"""Constants shared by the Incident Analysis domain."""

from enum import StrEnum


class IncidentCategory(StrEnum):
    TECHNICAL = "TECHNICAL"
    BILLING = "BILLING"
    ACCESS = "ACCESS"
    HR_QUERY = "HR_QUERY"
    COMPLAINT = "COMPLAINT"


class IncidentStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    DISCARDED = "DISCARDED"


class ValidationErrorCode(StrEnum):
    """Stable, privacy-safe codes for the seven specified validation rules."""

    MISSING_CLIENT_COMPANY = "missing_client_company"
    INVALID_CATEGORY = "invalid_category"
    INVALID_DESCRIPTION = "invalid_description"
    INVALID_AGENT_ID = "invalid_agent_id"
    INVALID_EMAIL = "invalid_email"
    CLOSED_WITHOUT_SATISFACTION_SCORE = "closed_without_satisfaction_score"
    SATISFACTION_SCORE_OUT_OF_RANGE = "satisfaction_score_out_of_range"


VALID_CATEGORIES = tuple(IncidentCategory)
VALID_STATUSES = tuple(IncidentStatus)
VALIDATION_ERROR_CODES = tuple(ValidationErrorCode)
