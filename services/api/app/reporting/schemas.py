"""Validated contracts for persisted weekly reporting data."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pipeline_name: str
    week_start: date
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    finished_at: datetime | None = None
    records_processed: int = Field(ge=0)
    records_inserted: int = Field(ge=0)
    records_updated: int = Field(ge=0)
    records_rejected: int = Field(ge=0)
    error_message: str | None = None
    trigger_type: Literal["scheduled", "manual"]


class PipelineRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    week_start: date | None = None

    @field_validator("week_start")
    @classmethod
    def require_monday(cls, value: date | None) -> date | None:
        if value is not None and value.weekday() != 0:
            raise ValueError("week_start must be a Monday (ISO week start)")
        return value


class PipelineRunAccepted(BaseModel):
    run_id: UUID
    pipeline_name: str
    week_start: date
    status: Literal["scheduled"] = "scheduled"
    trigger_type: Literal["manual"] = "manual"


class WeeklyPerformanceResponse(BaseModel):
    office: Literal["Valencia", "Miami"]
    programme_id: str
    week_start: date
    total_material_cost: Decimal
    kits_delivered_count: int = Field(ge=0)
    shortage_events_count: int = Field(ge=0)
    cost_variance_events_count: int = Field(ge=0)
    currency: Literal["EUR", "USD"]
    computed_at: datetime
