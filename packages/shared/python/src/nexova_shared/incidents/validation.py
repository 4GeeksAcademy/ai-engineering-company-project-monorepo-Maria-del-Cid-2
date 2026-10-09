"""Pure validation shared by the Incident Manager API and seed script."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

INCIDENT_CATEGORIES = (
    "technical_failure",
    "process_error",
    "client_complaint",
    "candidate_issue",
    "staff_issue",
    "sla_breach",
    "data_quality",
    "other",
)
INCIDENT_STATUSES = ("open", "in_progress", "resolved", "discarded")
INCIDENT_ORIGINS = ("customer", "branch", "internal")
INCIDENT_BRANCHES = ("central", "valencia_operations", "miami_office", "remote")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Safe validation result that identifies a user-facing field."""

    field: str
    message: str


def validate_incident_values(values: Mapping[str, object]) -> tuple[ValidationIssue, ...]:
    """Validate fields shared by API input and transformed seed records."""

    issues: list[ValidationIssue] = []
    _require_text(values, "title", issues, max_length=120)
    _require_text(values, "description", issues)
    _require_choice(values, "category", INCIDENT_CATEGORIES, issues)
    _require_choice(values, "status", INCIDENT_STATUSES, issues)
    _require_choice(values, "origin", INCIDENT_ORIGINS, issues)
    _require_choice(values, "branch", INCIDENT_BRANCHES, issues)
    return tuple(issues)


def _require_text(
    values: Mapping[str, object],
    field: str,
    issues: list[ValidationIssue],
    *,
    max_length: int | None = None,
) -> None:
    value = values.get(field)
    if not isinstance(value, str) or not value.strip():
        issues.append(ValidationIssue(field, f"{field} is required."))
        return
    if max_length is not None and len(value.strip()) > max_length:
        issues.append(ValidationIssue(field, f"{field} must be at most {max_length} characters."))


def _require_choice(
    values: Mapping[str, object],
    field: str,
    allowed: tuple[str, ...],
    issues: list[ValidationIssue],
) -> None:
    if values.get(field) not in allowed:
        issues.append(ValidationIssue(field, f"{field} has an unsupported value."))
