"""Privacy-safe validation of normalized incident rows."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import IncidentCategory, IncidentStatus, ValidationErrorCode
from .csv_reader import NormalizedIncidentRow
from .models import IncidentRecord


_AGENT_ID_PATTERN = re.compile(r"^AGT-\d{2}$")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validation outcome containing only safe error codes and domain data."""

    is_valid: bool
    errors: tuple[ValidationErrorCode, ...] = ()
    record: IncidentRecord | None = None


def validate_incident(row: NormalizedIncidentRow) -> ValidationResult:
    """Validate one normalized row against the seven specified business rules.

    The returned result never contains the source row or its customer email.
    Errors are stable enum codes, allowing CLI/API layers to present safe labels.
    """

    errors: list[ValidationErrorCode] = []

    if not row.client_company.strip():
        errors.append(ValidationErrorCode.MISSING_CLIENT_COMPANY)

    category = _parse_category(row.category.strip())
    if category is None:
        errors.append(ValidationErrorCode.INVALID_CATEGORY)

    if len(row.description.strip()) < 5:
        errors.append(ValidationErrorCode.INVALID_DESCRIPTION)

    if not _AGENT_ID_PATTERN.fullmatch(row.agent_id.strip()):
        errors.append(ValidationErrorCode.INVALID_AGENT_ID)

    if not row.customer_email.strip() or "@" not in row.customer_email:
        errors.append(ValidationErrorCode.INVALID_EMAIL)

    status = _parse_status(row.status.strip())
    if status is IncidentStatus.CLOSED and row.satisfaction_score is None:
        errors.append(ValidationErrorCode.CLOSED_WITHOUT_SATISFACTION_SCORE)

    score = row.satisfaction_score
    if score is not None and (not isinstance(score, int) or not 1 <= score <= 5):
        errors.append(ValidationErrorCode.SATISFACTION_SCORE_OUT_OF_RANGE)

    if errors:
        return ValidationResult(is_valid=False, errors=tuple(errors))

    # Status is part of the input contract. A malformed status cannot produce a
    # domain record, although it has no additional validation code in this unit.
    if status is None or category is None:
        raise ValueError("validated row contains an unsupported domain value")

    return ValidationResult(
        is_valid=True,
        record=IncidentRecord(
            category=category,
            status=status,
            satisfaction_score=score,
        ),
    )


def _parse_category(value: str) -> IncidentCategory | None:
    try:
        return IncidentCategory(value)
    except ValueError:
        return None


def _parse_status(value: str) -> IncidentStatus | None:
    try:
        return IncidentStatus(value)
    except ValueError:
        return None
