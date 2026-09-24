"""Privacy-safe CSV export of aggregate incident analysis results."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TextIO

from .models import IncidentAnalysisResult


EXPORT_COLUMNS = ("metric", "dimension", "value")


def export_analysis_csv(
    result: IncidentAnalysisResult,
    destination: str | Path | TextIO,
) -> None:
    """Write aggregate metrics as one ``metric,dimension,value`` row each.

    Only fields from ``IncidentAnalysisResult`` are exported. Raw incident rows
    and customer email addresses are not accepted or serialized.
    """

    if hasattr(destination, "write"):
        _write_rows(destination, result)
        return

    path = Path(destination)
    with path.open("w", encoding="utf-8", newline="") as handle:
        _write_rows(handle, result)


def _write_rows(handle: TextIO, result: IncidentAnalysisResult) -> None:
    writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    _write_metric(writer, "total_records", "all", result.total_records)
    _write_metric(writer, "valid_records", "all", result.valid_records)
    _write_metric(writer, "invalid_records", "all", result.invalid_records)

    for category, count in result.by_category.items():
        _write_metric(writer, "records_by_category", category.value, count)

    for status, count in result.by_status.items():
        _write_metric(writer, "records_by_status", status.value, count)

    for score, count in result.satisfaction_distribution.items():
        _write_metric(writer, "satisfaction_distribution", str(score), count)

    if result.average_satisfaction is not None:
        _write_metric(writer, "average_satisfaction", "closed_tickets", result.average_satisfaction)

    for error_code, count in result.invalid_by_type.items():
        _write_metric(writer, "invalid_by_type", error_code.value, count)


def _write_metric(
    writer: csv.DictWriter[str],
    metric: str,
    dimension: str,
    value: int | float,
) -> None:
    writer.writerow({"metric": metric, "dimension": dimension, "value": value})
