"""Persistence operations for the Centralized Incident Manager."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from tinydb import Query, TinyDB
from tinydb.table import Document, Table

from .manager_models import (
    INCIDENT_BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
    VALID_STATUS_TRANSITIONS,
    Incident,
    IncidentCreate,
    IncidentStatus,
    IncidentSummary,
)


class IncidentRepository:
    """Keep TinyDB details out of HTTP and seed adapters."""

    def __init__(self, database: TinyDB) -> None:
        self.database = database
        self.incidents: Table = database.table("incidents")
        self.seed_keys: Table = database.table("incident_seed_keys")

    def list(
        self,
        *,
        status: IncidentStatus | None = None,
        origin: str | None = None,
        branch: str | None = None,
        category: str | None = None,
    ) -> list[Incident]:
        incidents = [Incident.model_validate(record) for record in self.incidents.all()]
        return [
            incident
            for incident in incidents
            if (status is None or incident.status == status)
            and (origin is None or incident.origin == origin)
            and (branch is None or incident.branch == branch)
            and (category is None or incident.category == category)
        ]

    def get(self, incident_id: int) -> Incident | None:
        record = self.incidents.get(doc_id=incident_id)
        return Incident.model_validate(record) if record is not None else None

    def create(self, payload: IncidentCreate, *, created_at: datetime | None = None) -> Incident:
        incident_id = max((record.doc_id for record in self.incidents), default=0) + 1
        timestamp = created_at or datetime.now(timezone.utc)
        incident = Incident(
            id=incident_id,
            created_at=timestamp,
            updated_at=timestamp,
            **payload.model_dump(),
        )
        self.incidents.insert(Document(incident.model_dump(mode="json"), doc_id=incident_id))
        return incident

    def update_status(self, incident_id: int, next_status: IncidentStatus) -> Incident | None:
        current = self.get(incident_id)
        if current is None:
            return None
        if next_status not in VALID_STATUS_TRANSITIONS[current.status]:
            raise ValueError(f"Cannot transition from {current.status} to {next_status}")

        updated = current.model_copy(
            update={"status": next_status, "updated_at": datetime.now(timezone.utc)}
        )
        self.incidents.update(updated.model_dump(mode="json"), doc_ids=[incident_id])
        return updated

    def summary(self) -> IncidentSummary:
        incidents = self.list()
        return IncidentSummary(
            total=len(incidents),
            by_status=_count(incidents, "status", INCIDENT_STATUSES),
            by_category=_count(incidents, "category", INCIDENT_CATEGORIES),
            by_origin=_count(incidents, "origin", INCIDENT_ORIGINS),
            by_branch=_count(incidents, "branch", INCIDENT_BRANCHES),
        )

    def has_seed_key(self, key: str) -> bool:
        return self.seed_keys.search(Query().key == key) != []

    def remember_seed_key(self, key: str, incident_id: int) -> None:
        self.seed_keys.insert({"key": key, "incident_id": incident_id})


def _count(
    incidents: Iterable[Incident],
    field_name: str,
    values: Iterable[str],
) -> dict[str, int]:
    counts = {value: 0 for value in values}
    for incident in incidents:
        counts[getattr(incident, field_name)] += 1
    return counts
