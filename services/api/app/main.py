"""FastAPI application for the Nexova Incident Analysis service."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import time
import uuid
from io import StringIO
from pathlib import Path
from uuid import UUID

from celery.result import AsyncResult
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from app.middleware import TimingMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .celery_app import celery_app
from .incidents.csv_reader import CsvReadError, read_incidents_csv
from .incidents.export import export_analysis_csv
from .incidents.constants import IncidentCategory, IncidentStatus, ValidationErrorCode
from .incidents.models import IncidentAnalysisResult
from .incidents.schemas import (
    IncidentAnalysisResponse,
    IncidentAnalysisTaskAccepted,
    IncidentAnalysisTaskStatus,
)
from .tasks.incident_analysis import analyze_incidents_task, get_incident_upload_dir
from .incidents.manager_router import router as incident_manager_router
from .inventory.router import router as inventory_router
from .suppliers.router import router as suppliers_router
from .auth.routers.auth_router import router as auth_router
from .auth.routers.users_router import router as users_router
from .auth.routers.profiles_router import router as profiles_router
from .telemetry.emitter import emit_event
from .telemetry.router import router as telemetry_router
from .reporting.router import router as reporting_router

_DEFAULT_CORS_ORIGINS = ("http://localhost:3000",)
logger = logging.getLogger(__name__)

# Ensure the root logger outputs to stderr so that child loggers (e.g.
# app.middleware.timing) produce visible output.  Uvicorn's own logging
# configuration does not attach a handler to the root logger, meaning
# messages from non-uvicorn loggers are silently discarded otherwise.
logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")


def _sanitize_validation_errors(exc: RequestValidationError) -> list[dict[str, object]]:
    """Remove request values and exception context from validation errors."""
    sensitive_keys = {"input", "ctx"}
    return [
        {key: value for key, value in error.items() if key not in sensitive_keys}
        for error in exc.errors()
    ]


def _emit_backend_error(request: Request, exc: Exception) -> None:
    """Emit an ``unhandled_api_error`` telemetry event for unexpected failures.

    This is called from the global ``Exception`` handler. Logs a warning
    if the emission itself fails, but never propagates the exception.
    """
    try:
        path = str(request.url.path)
        method = request.method if request.method else "?"
        emit_event(
            "unhandled_api_error",
            {
                "method": method,
                "path": path,
                "status_code": 500,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:200] if str(exc) else None,
            },
        )
    except Exception:
        logger.warning("Failed to emit unhandled_api_error event", exc_info=True)


def get_default_cors_origins() -> list[str]:
    """Return local and, when available, the exact current Codespaces origin."""
    origins = list(_DEFAULT_CORS_ORIGINS)
    codespace_name = os.getenv("CODESPACE_NAME", "").strip()
    forwarding_domain = os.getenv(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev"
    ).strip().strip("/")
    if codespace_name and forwarding_domain:
        origins.append(f"https://{codespace_name}-3000.{forwarding_domain}")
    return origins


def get_cors_origins() -> list[str]:
    """Return explicit browser origins from CORS_ORIGINS or development defaults."""
    configured_origins = os.getenv("CORS_ORIGINS")
    origins = (
        [
            origin.strip().rstrip("/")
            for origin in configured_origins.split(",")
            if origin.strip().rstrip("/")
        ]
        if configured_origins is not None
        else get_default_cors_origins()
    )
    if "*" in origins:
        raise ValueError("CORS_ORIGINS must contain explicit origins, not '*'")
    return origins


app = FastAPI(title="Nexova Incident Analysis API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TimingMiddleware)
app.include_router(suppliers_router)
app.include_router(inventory_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(incident_manager_router)
app.include_router(telemetry_router)
app.include_router(reporting_router)
MAX_INCIDENT_UPLOAD_BYTES = int(os.getenv("INCIDENT_ANALYSIS_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
INCIDENT_UPLOAD_RETENTION_SECONDS = int(os.getenv("INCIDENT_ANALYSIS_UPLOAD_RETENTION_SECONDS", "86400"))


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return user-safe 400 validation errors for Incident Manager requests."""

    manager_path = request.url.path == "/api/incidents" or request.url.path.startswith(
        "/api/incidents/"
    )
    analysis_path = request.url.path == "/api/incidents/analyze" or request.url.path.startswith(
        "/api/incidents/tasks/"
    )
    if request.url.path.startswith("/api/tasks/"):
        analysis_path = True
    if not manager_path or analysis_path:
        return JSONResponse(
            status_code=422,
            content={"detail": jsonable_encoder(_sanitize_validation_errors(exc))},
        )

    first_error = exc.errors()[0]
    location = first_error.get("loc", ())
    field = next((str(item) for item in reversed(location) if isinstance(item, str)), "request")
    return JSONResponse(
        status_code=400,
        content={
            "field": field,
            "message": "El valor indicado no es válido.",
        },
    )
@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Never expose implementation details from an unexpected server error."""

    logger.error(
        "unexpected request failure path=%s exception_type=%s correlation_id=%s",
        request.url.path,
        type(exc).__name__,
        request.headers.get("X-Request-ID") or "-",
    )

    _emit_backend_error(request, exc)

    return JSONResponse(
        status_code=500,
        content={"message": "No se pudo completar la operación. Inténtalo de nuevo."},
    )


@app.post(
    "/api/incidents/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=IncidentAnalysisTaskAccepted,
)
async def analyze_uploaded_incidents(
    file: UploadFile = File(...),
) -> IncidentAnalysisTaskAccepted:
    """Store a bounded CSV upload and enqueue asynchronous aggregate analysis."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="A CSV file is required")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV")

    upload_dir = get_incident_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    upload_id = uuid.uuid4().hex
    final_path = upload_dir / f"{upload_id}.csv"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=upload_dir, prefix=".upload-", suffix=".tmp", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            total_bytes = 0
            while chunk := await file.read(64 * 1024):
                total_bytes += len(chunk)
                if total_bytes > MAX_INCIDENT_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded CSV exceeds the size limit")
                temp_file.write(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

        # Validate UTF-8 and CSV structure before accepting the task. The worker
        # repeats the parse from the shared file and performs business analysis.
        try:
            rows = read_incidents_csv(temp_path)
        except (UnicodeDecodeError, CsvReadError) as exc:
            raise HTTPException(status_code=400, detail="Invalid CSV file") from exc
        if not rows:
            raise HTTPException(status_code=400, detail="CSV must contain at least one data row")
        os.chmod(temp_path, 0o600)
        temp_path.replace(final_path)
        try:
            task = analyze_incidents_task.apply_async(args=[upload_id])
        except Exception as exc:
            final_path.unlink(missing_ok=True)
            logger.warning("Incident analysis task submission failed exception_type=%s", type(exc).__name__)
            raise HTTPException(status_code=503, detail="Analysis queue is temporarily unavailable") from exc
        _cleanup_stale_uploads(upload_dir, keep=final_path)
        return IncidentAnalysisTaskAccepted(task_id=task.id)
    except CsvReadError as exc:
        raise HTTPException(status_code=400, detail="Invalid CSV file") from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        await file.close()


def _cleanup_stale_uploads(upload_dir: Path, keep: Path) -> None:
    """Remove stale temporary uploads left by interrupted API processes."""

    cutoff = time.time() - INCIDENT_UPLOAD_RETENTION_SECONDS
    try:
        for path in upload_dir.iterdir():
            if path == keep or not path.is_file():
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Stale incident upload cleanup failed")
    except OSError:
        logger.warning("Incident upload directory cleanup failed")


def _get_completed_result(task_id: str) -> dict[str, object]:
    try:
        UUID(task_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc

    result = AsyncResult(task_id, app=celery_app)
    if result.state != "SUCCESS" or not isinstance(result.result, dict):
        raise HTTPException(status_code=404, detail="Completed analysis result not found")
    return result.result


@app.get("/api/tasks/{task_id}", response_model=IncidentAnalysisTaskStatus)
async def get_task_status(task_id: str) -> IncidentAnalysisTaskStatus:
    """Return the state and safe aggregate result of a Celery task."""

    try:
        UUID(task_id)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc

    task = AsyncResult(task_id, app=celery_app)
    state = task.state
    payload: dict[str, object] = {
        "task_id": task_id,
        "status": state.lower()
        if state in {"PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY", "REVOKED"}
        else "pending",
    }
    if task.state == "SUCCESS" and isinstance(task.result, dict):
        payload["result"] = task.result
    elif task.state == "FAILURE":
        payload["error"] = "Analysis failed. Please upload the file again."
    return IncidentAnalysisTaskStatus.model_validate(payload)


@app.get("/api/incidents/tasks/{task_id}/export")
async def export_task_result(task_id: str) -> StreamingResponse:
    """Download the aggregate CSV for a specific completed task."""

    serialized_result = _get_completed_result(task_id)
    try:
        result = IncidentAnalysisResponse.model_validate(serialized_result)
        domain_result = IncidentAnalysisResult(
            total_records=result.total_records,
            valid_records=result.valid_records,
            invalid_records=result.invalid_records,
            by_category={IncidentCategory(key): value for key, value in result.by_category.items()},
            by_status={IncidentStatus(key): value for key, value in result.by_status.items()},
            satisfaction_distribution={int(key): value for key, value in result.satisfaction_distribution.items()},
            average_satisfaction=result.average_satisfaction,
            invalid_by_type={ValidationErrorCode(key): value for key, value in result.invalid_by_type.items()},
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=500, detail="Stored analysis result is invalid") from exc
    output = StringIO()
    export_analysis_csv(domain_result, output)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )
