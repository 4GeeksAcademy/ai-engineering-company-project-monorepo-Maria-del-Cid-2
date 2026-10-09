"""FastAPI application for the Nexova Incident Analysis service."""

from __future__ import annotations

import io
import os
from io import StringIO

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .incidents.analysis import analyze_incidents
from .incidents.csv_reader import CsvReadError, read_incidents_csv
from .incidents.export import export_analysis_csv
from .incidents.models import IncidentAnalysisResult
from .incidents.manager_router import router as incident_manager_router
from .suppliers.router import router as suppliers_router
from .auth.routers.auth_router import router as auth_router
from .auth.routers.users_router import router as users_router
from .auth.routers.profiles_router import router as profiles_router

_DEFAULT_CORS_ORIGINS = ("http://localhost:3000",)


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
app.include_router(suppliers_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(incident_manager_router)
_latest_result: IncidentAnalysisResult | None = None


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return user-safe 400 validation errors for Incident Manager requests."""

    manager_path = request.url.path == "/api/incidents" or request.url.path.startswith(
        "/api/incidents/"
    )
    analysis_path = request.url.path in {
        "/api/incidents/analyze",
        "/api/incidents/results/export",
    }
    if not manager_path or analysis_path:
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})

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
async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    """Never expose implementation details from an unexpected server error."""

    return JSONResponse(
        status_code=500,
        content={"message": "No se pudo completar la operación. Inténtalo de nuevo."},
    )


@app.post("/api/incidents/analyze")
async def analyze_uploaded_incidents(file: UploadFile = File(...)) -> dict[str, object]:
    """Analyze an uploaded CSV and return aggregate, privacy-safe metrics."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="A CSV file is required")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a CSV")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty")

    try:
        rows = read_incidents_csv(io.StringIO(content.decode("utf-8-sig")))
        if not rows:
            raise CsvReadError("CSV must contain at least one data row")
        result = analyze_incidents(rows)
    except (UnicodeDecodeError, CsvReadError) as exc:
        raise HTTPException(status_code=400, detail="Invalid CSV file") from exc

    global _latest_result
    _latest_result = result
    return _serialize_result(result)


@app.get("/api/incidents/results/export")
async def export_latest_result() -> StreamingResponse:
    """Download the latest aggregate result as a privacy-safe CSV."""

    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No analysis result available")

    output = StringIO()
    export_analysis_csv(_latest_result, output)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=results.csv"},
    )


def _serialize_result(result: IncidentAnalysisResult) -> dict[str, object]:
    """Serialize only aggregate result fields; never raw input fields."""

    return {
        "total_records": result.total_records,
        "valid_records": result.valid_records,
        "invalid_records": result.invalid_records,
        "by_category": {category.value: count for category, count in result.by_category.items()},
        "by_status": {status.value: count for status, count in result.by_status.items()},
        "satisfaction_distribution": {
            str(score): count for score, count in result.satisfaction_distribution.items()
        },
        "average_satisfaction": result.average_satisfaction,
        "invalid_by_type": {
            error.value: count for error, count in result.invalid_by_type.items()
        },
    }
