"""Contracts for the persistent Centralized Incident Manager."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic import model_validator

from nexova_shared.incidents.validation import (
    INCIDENT_BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
    validate_incident_values,
)

IncidentCategory = Literal[
    "technical_failure",
    "process_error",
    "client_complaint",
    "candidate_issue",
    "staff_issue",
    "sla_breach",
    "data_quality",
    "other",
]
IncidentStatus = Literal["open", "in_progress", "resolved", "discarded"]
IncidentOrigin = Literal["customer", "branch", "internal"]
IncidentBranch = Literal["central", "valencia_operations", "miami_office", "remote"]

VALID_STATUS_TRANSITIONS: dict[IncidentStatus, tuple[IncidentStatus, ...]] = {
    "open": ("in_progress", "discarded"),
    "in_progress": ("resolved", "discarded"),
    "resolved": (),
    "discarded": (),
}


class IncidentCreate(BaseModel):
    """Fields accepted when creating an incident."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    category: IncidentCategory
    status: IncidentStatus = "open"
    origin: IncidentOrigin
    branch: IncidentBranch

    @model_validator(mode="after")
    def validate_shared_values(self) -> "IncidentCreate":
        issues = validate_incident_values(self.model_dump())
        if issues:
            raise ValueError(" ".join(issue.message for issue in issues))
        return self


class IncidentStatusUpdate(BaseModel):
    """Payload accepted by the status-only update endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: IncidentStatus


class Incident(BaseModel):
    """Persisted incident record. Source ticket identifiers are not stored."""

    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1)
    category: IncidentCategory
    status: IncidentStatus
    origin: IncidentOrigin
    branch: IncidentBranch
    created_at: datetime
    updated_at: datetime


class IncidentSummary(BaseModel):
    """Complete aggregate response, including zero-valued dimensions."""

    total: int = Field(ge=0)
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_origin: dict[str, int]
    by_branch: dict[str, int]
