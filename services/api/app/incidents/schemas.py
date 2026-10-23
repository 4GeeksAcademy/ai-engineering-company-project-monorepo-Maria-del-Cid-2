"""Pydantic request/response schemas for the Incident Analysis API.

These models document the public API contract for the
``/api/incidents/analyze`` endpoint.  They are intentionally
separate from the internal domain dataclasses in ``models.py``
so that the serialization boundary is explicit.
"""

from __future__ import annotations

from pydantic import BaseModel


class IncidentAnalysisResponse(BaseModel):
    """Aggregate, privacy-safe response returned by ``POST /api/incidents/analyze``.

    Every field is derived from validated rows; no raw CSV column
    (customer email, ticket id, description) is ever exposed.
    """

    total_records: int
    valid_records: int
    invalid_records: int
    by_category: dict[str, int]
    by_status: dict[str, int]
    satisfaction_distribution: dict[str, int]
    average_satisfaction: float | None = None
    invalid_by_type: dict[str, int]