"""Privacy-safe aggregate analysis for validated incident rows."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .constants import IncidentCategory, IncidentStatus, ValidationErrorCode
from .csv_reader import NormalizedIncidentRow
from .models import IncidentAnalysisResult
from .validation import validate_incident


def analyze_incidents(
    rows: Iterable[NormalizedIncidentRow],
) -> IncidentAnalysisResult:
    """Validate and aggregate incident rows without retaining sensitive input."""

    total_records = 0
    valid_records = 0
    invalid_records = 0
    by_category: Counter[IncidentCategory] = Counter()
    by_status: Counter[IncidentStatus] = Counter()
    satisfaction_distribution: Counter[int] = Counter()
    invalid_by_type: Counter[ValidationErrorCode] = Counter()
    satisfaction_scores: list[int] = []

    for row in rows:
        total_records += 1
        validation = validate_incident(row)
        if not validation.is_valid:
            invalid_records += 1
            invalid_by_type.update(validation.errors)
            continue

        valid_records += 1
        assert validation.record is not None
        record = validation.record
        by_category[record.category] += 1
        by_status[record.status] += 1

        if record.status is IncidentStatus.CLOSED and record.satisfaction_score is not None:
            satisfaction_distribution[record.satisfaction_score] += 1
            satisfaction_scores.append(record.satisfaction_score)

    average = (
        round(sum(satisfaction_scores) / len(satisfaction_scores), 2)
        if satisfaction_scores
        else None
    )
    return IncidentAnalysisResult(
        total_records=total_records,
        valid_records=valid_records,
        invalid_records=invalid_records,
        by_category=dict(by_category),
        by_status=dict(by_status),
        satisfaction_distribution=dict(satisfaction_distribution),
        average_satisfaction=average,
        invalid_by_type=dict(invalid_by_type),
    )


def analyze_incidents_csv(source: str) -> IncidentAnalysisResult:
    """Read a CSV source and return its privacy-safe aggregate analysis."""

    from .csv_reader import read_incidents_csv

    return analyze_incidents(read_incidents_csv(source))
