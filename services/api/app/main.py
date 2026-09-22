"""FastAPI application for the Nexova Incident Analysis service."""

from __future__ import annotations

import io
from io import StringIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from .incidents.analysis import analyze_incidents
from .incidents.csv_reader import CsvReadError, read_incidents_csv
from .incidents.export import export_analysis_csv
from .incidents.models import IncidentAnalysisResult

app = FastAPI(title="Nexova Incident Analysis API", version="0.1.0")
_latest_result: IncidentAnalysisResult | None = None


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
