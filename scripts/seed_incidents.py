"""Seed the persistent Incident Manager from the official historical CSV."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "python" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from nexova_shared.incidents.validation import validate_incident_values  # noqa: E402
from app.incidents.csv_reader import NormalizedIncidentRow, read_incidents_csv  # noqa: E402
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
    database = get_database()
    invalid_rows: list[int] = []
    inserted = 0
    try:
        repository = IncidentRepository(database)
        for row_number, row in enumerate(read_incidents_csv(csv_path), start=2):
            transformed = transform_row(row)
            if transformed is None:
                invalid_rows.append(row_number)
                continue

            key, payload, created_at = transformed
            if repository.has_seed_key(key):
                continue
            incident = repository.create(payload, created_at=created_at)
            repository.remember_seed_key(key, incident.id)
            inserted += 1

        summary = repository.summary()
        result = {
            "inserted": inserted,
            "invalid_rows": invalid_rows,
            "total": summary.total,
            "by_status": summary.by_status,
            "by_category": summary.by_category,
        }
    finally:
        database.close()

    status_counts = result["by_status"]
    category_counts = result["by_category"]
    if result["total"] != 96 or any(
        status_counts.get(key, 0) != value for key, value in EXPECTED_STATUS_COUNTS.items()
    ):
        raise RuntimeError(f"Unexpected seeded status totals: {result}")
    if any(category_counts.get(key, 0) != value for key, value in EXPECTED_CATEGORY_COUNTS.items()):
        raise RuntimeError(f"Unexpected seeded category totals: {result}")
    return result


def main() -> None:
    result = seed_incidents()
    print(f"Inserted {result['inserted']} incidents.")
    print(f"Invalid rows: {result['invalid_rows'] or 'none'}")
    print(f"Total valid incidents: {result['total']}")
    print(f"By status: {result['by_status']}")
    print(f"By category: {result['by_category']}")


if __name__ == "__main__":
    main()