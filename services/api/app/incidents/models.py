"""Privacy-safe domain models for Incident Analysis.

These models describe the contract between the future CSV reader, validator,
analysis engine, CLI, and API. They intentionally do not model raw CSV rows
or expose customer email addresses in analysis results.
"""

from dataclasses import dataclass, field
from typing import TypeAlias

from .constants import (
    IncidentCategory,
    IncidentStatus,
    ValidationErrorCode,
)

ScoreDistribution: TypeAlias = dict[int, int]
CountByCategory: TypeAlias = dict[IncidentCategory, int]
CountByStatus: TypeAlias = dict[IncidentStatus, int]
CountByValidationError: TypeAlias = dict[ValidationErrorCode, int]


@dataclass(frozen=True, slots=True)
class IncidentRecord:
    """Validated domain representation without customer email data."""

    category: IncidentCategory
    status: IncidentStatus
    satisfaction_score: int | None = None


@dataclass(frozen=True, slots=True)
class IncidentAnalysisResult:
    """Aggregated analysis output safe for API and CSV serialization."""

    total_records: int
    valid_records: int
    invalid_records: int
    by_category: CountByCategory = field(default_factory=dict)
    by_status: CountByStatus = field(default_factory=dict)
    satisfaction_distribution: ScoreDistribution = field(default_factory=dict)
    average_satisfaction: float | None = None
    invalid_by_type: CountByValidationError = field(default_factory=dict)
