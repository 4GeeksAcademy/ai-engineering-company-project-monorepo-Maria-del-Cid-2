"""Safe serialization helpers for Incident Analysis task results."""

from __future__ import annotations

from app.incidents.models import IncidentAnalysisResult


def serialize_analysis_result(result: IncidentAnalysisResult) -> dict[str, object]:
    """Serialize aggregate metrics only; never include source-row values."""

    return {
        "total_records": result.total_records,
        "valid_records": result.valid_records,
        "invalid_records": result.invalid_records,
        "by_category": {
            category.value: count for category, count in result.by_category.items()
        },
        "by_status": {status.value: count for status, count in result.by_status.items()},
        "satisfaction_distribution": {
            str(score): count
            for score, count in result.satisfaction_distribution.items()
        },
        "average_satisfaction": result.average_satisfaction,
        "invalid_by_type": {
            error.value: count for error, count in result.invalid_by_type.items()
        },
    }