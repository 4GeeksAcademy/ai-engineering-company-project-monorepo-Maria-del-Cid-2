"""CSV input reader and normalizer for Incident Analysis.

This module is deliberately limited to file-shape handling and normalization.
Business validation belongs to the next unit and consumes ``NormalizedIncidentRow``.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO


REQUIRED_COLUMNS = (
    "ticket_id",
    "date",
    "client_company",
    "category",
    "description",
    "agent_id",
    "status",
    "customer_email",
    "satisfaction_score",
)


class CsvReadError(ValueError):
    """Raised when the CSV cannot be read as the expected tabular input."""


@dataclass(frozen=True, slots=True)
class NormalizedIncidentRow:
    """One CSV row with whitespace normalized and score converted when possible.

    ``customer_email`` is retained only as input for the future validator.  It is
    excluded from the representation to prevent accidental logging or display.
    """

    ticket_id: str
    date: str
    client_company: str
    category: str
    description: str
    agent_id: str
    status: str
    customer_email: str = field(repr=False)
    satisfaction_score: int | str | None = None

def read_incidents_csv(source: str | Path | TextIO) -> list[NormalizedIncidentRow]:
    """Read and normalize an Incident Analysis CSV.

    The function handles only UTF-8 CSV structure: encoding, delimiter,
    required columns, row width, trimming, and optional score conversion.
    It does not apply any of the seven business validation rules.
    """

    if hasattr(source, "read"):
        return _read_rows(source)

    path = Path(source)
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return _read_rows(handle)
    except UnicodeDecodeError as exc:
        raise CsvReadError("CSV must be UTF-8 encoded") from exc
    except OSError as exc:
        raise CsvReadError(f"Unable to read CSV file: {path}") from exc


def _read_rows(handle: TextIO) -> list[NormalizedIncidentRow]:
    reader = csv.DictReader(handle, delimiter=",")
    if reader.fieldnames is None or not any(name.strip() for name in reader.fieldnames):
        raise CsvReadError("CSV must contain a header row")

    fieldnames = [name.strip() for name in reader.fieldnames]
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise CsvReadError("CSV is missing required columns: " + ", ".join(missing))

    normalized_keys = dict(zip(reader.fieldnames, fieldnames, strict=True))
    rows: list[NormalizedIncidentRow] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise CsvReadError(f"CSV row {row_number} has more columns than its header")
        if any(value is None for value in row.values()):
            raise CsvReadError(f"CSV row {row_number} has fewer columns than its header")
        rows.append(_normalize_row({normalized_keys[key]: value for key, value in row.items()}))
    return rows


def _normalize_row(row: dict[str, str]) -> NormalizedIncidentRow:
    values = {key.strip(): value.strip() for key, value in row.items()}
    score_text = values["satisfaction_score"]
    score: int | str | None
    if not score_text:
        score = None
    else:
        try:
            score = int(score_text)
        except ValueError:
            score = score_text

    return NormalizedIncidentRow(
        ticket_id=values["ticket_id"],
        date=values["date"],
        client_company=values["client_company"],
        category=values["category"],
        description=values["description"],
        agent_id=values["agent_id"],
        status=values["status"],
        customer_email=values["customer_email"],
        satisfaction_score=score,
    )
