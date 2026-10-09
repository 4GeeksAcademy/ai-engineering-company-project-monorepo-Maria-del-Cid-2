"""HTTP endpoints for the persistent Centralized Incident Manager."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user

from .manager_database import get_database
from .manager_models import (
    Incident,
    IncidentBranch,
    IncidentCategory,
    IncidentCreate,
    IncidentOrigin,
    IncidentStatus,
    IncidentStatusUpdate,
    IncidentSummary,
)
from .manager_repository import IncidentRepository

router = APIRouter(
    prefix="/api/incidents",
    tags=["incident-manager"],
    dependencies=[Depends(get_current_user)],
)


def get_repository() -> Generator[IncidentRepository, None, None]:
    database = get_database()
    try:
        yield IncidentRepository(database)
    finally:
        database.close()


@router.post("", response_model=Incident, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    repository: IncidentRepository = Depends(get_repository),
) -> Incident:
    return repository.create(payload)


@router.get("", response_model=list[Incident])
def list_incidents(
    status_filter: IncidentStatus | None = Query(default=None, alias="status"),
    origin: IncidentOrigin | None = Query(default=None),
    branch: IncidentBranch | None = Query(default=None),
    category: IncidentCategory | None = Query(default=None),
    repository: IncidentRepository = Depends(get_repository),
) -> list[Incident]:
    return repository.list(
        status=status_filter,
        origin=origin,
        branch=branch,
        category=category,
    )


@router.get("/summary", response_model=IncidentSummary)
def incident_summary(repository: IncidentRepository = Depends(get_repository)) -> IncidentSummary:
    return repository.summary()


@router.get("/{incident_id}", response_model=Incident)
def get_incident(
    incident_id: int,
    repository: IncidentRepository = Depends(get_repository),
) -> Incident:
    incident = repository.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.patch("/{incident_id}/status", response_model=Incident)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    repository: IncidentRepository = Depends(get_repository),
) -> Incident:
    if repository.get(incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    try:
        incident = repository.update_status(incident_id, payload.status)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "field": "status",
                "message": "La transición de estado solicitada no está permitida.",
            },
        )
    assert incident is not None
    return incident
