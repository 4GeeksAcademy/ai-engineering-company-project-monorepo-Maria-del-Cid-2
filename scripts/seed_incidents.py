"""Seed the persistent Incident Manager from the official historical CSV."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from nexova_shared.incidents.validation import validate_incident_values  # noqa: E402
from app.incidents.csv_reader import CsvReadError, NormalizedIncidentRow, read_incidents_csv  # noqa: E402
from app.incidents.validation import validate_incident  # noqa: E402
from app.incidents.manager_database import get_database  # noqa: E402
from app.incidents.manager_models import IncidentCreate  # noqa: E402
from app.incidents.manager_repository import IncidentRepository  # noqa: E402

CSV_PATH = ROOT / "scripts" / "incidents-nexova.csv"
EXPECTED_STATUS_COUNTS = {"open": 27, "resolved": 56, "discarded": 13}
EXPECTED_CATEGORY_COUNTS = {
    "technical_failure": 49,
    "process_error": 35,
    "client_complaint": 12,
}
STATUS_MAP = {"OPEN": "open", "CLOSED": "resolved", "DISCARDED": "discarded"}
CATEGORY_MAP = {
    "TECHNICAL": "technical_failure",
    "BILLING": "process_error",
    "ACCESS": "technical_failure",
    "HR_QUERY": "process_error",
    "COMPLAINT": "client_complaint",
}


def transform_row(row: NormalizedIncidentRow) -> tuple[str, IncidentCreate, datetime] | None:
    validation = validate_incident(row)
    if not validation.is_valid or row.status not in STATUS_MAP or row.category not in CATEGORY_MAP:
        return None

    title = row.description[:120].strip()
    if not title:
        return None

    try:
        created_at = datetime.strptime(row.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    values = {
        "title": title,
        "description": row.description,
        "category": CATEGORY_MAP[row.category],
        "status": STATUS_MAP[row.status],
        "origin": "customer",
        "branch": "central",
    }
    if validate_incident_values(values):
        return None
    payload = IncidentCreate.model_validate(values)
    key = row.ticket_id or f"{title}|{created_at.isoformat()}"
    return key, payload, created_at


def seed_incidents(csv_path: Path = CSV_PATH) -> dict[str, object]:
    rows = read_incidents_csv(csv_path)
    invalid_rows: list[int] = []
    prepared_rows: list[tuple[str, IncidentCreate, datetime]] = []
    for row_number, row in enumerate(rows, start=2):
        transformed = transform_row(row)
        if transformed is None:
            invalid_rows.append(row_number)
            continue
        prepared_rows.append(transformed)

    imported_status_counts = {key: 0 for key in EXPECTED_STATUS_COUNTS}
    imported_category_counts = {key: 0 for key in EXPECTED_CATEGORY_COUNTS}
    for _, payload, _ in prepared_rows:
        imported_status_counts[payload.status] += 1
        imported_category_counts[payload.category] += 1

    if (
        imported_status_counts != EXPECTED_STATUS_COUNTS
        or imported_category_counts != EXPECTED_CATEGORY_COUNTS
    ):
        raise RuntimeError(
            "Unexpected imported incident totals: "
            f"status={imported_status_counts} category={imported_category_counts}"
        )

    database = get_database()
    inserted = 0
    try:
        repository = IncidentRepository(database)
        for key, payload, created_at in prepared_rows:
            if repository.has_seed_key(key):
                continue
            incident = repository.create(payload, created_at=created_at)
            repository.remember_seed_key(key, incident.id)
            inserted += 1

        summary = repository.summary()
        result = {
            "inserted": inserted,
            "invalid_rows": invalid_rows,
            "total": len(prepared_rows),
            "database_total": summary.total,
            "by_status": imported_status_counts,
            "by_category": imported_category_counts,
        }
    finally:
        database.close()

    return result


def main(csv_path: Path = CSV_PATH) -> int:
    try:
        result = seed_incidents(csv_path)
    except CsvReadError as exc:
        print(f"Error: unable to read incidents CSV: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError):
        print("Error: unable to seed incidents because the input or persistence operation failed.", file=sys.stderr)
        return 1

    print(f"Inserted {result['inserted']} incidents.")
    print(f"Invalid rows: {result['invalid_rows'] or 'none'}")
    print(f"Imported valid incidents: {result['total']}")
    print(f"Total incidents in database: {result['database_total']}")
    print(f"By status: {result['by_status']}")
    print(f"By category: {result['by_category']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())