"""Pandas ETL pipeline for telemetry analytics.

Reads events from the Supabase ``telemetry_events`` table via
``TELEMETRY_DATABASE_URL``, computes metrics **A1–A11** defined in
``docs/telemetry/telemetry-plan.md``, and returns DataFrames suitable for
dashboard rendering.

Usage (CLI)::

    python -m app.telemetry.report --help

Or import and call ``build_report()`` directly.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

TELEMETRY_DATABASE_URL_ENV = "TELEMETRY_DATABASE_URL"

_TELEMETRY_DATABASE_URL: str | None = None


def _get_database_url() -> str:
    global _TELEMETRY_DATABASE_URL
    if _TELEMETRY_DATABASE_URL is None:
        url = os.environ.get(TELEMETRY_DATABASE_URL_ENV, "").strip()
        if not url:
            print(
                f"Error: {TELEMETRY_DATABASE_URL_ENV} is not set.",
                file=sys.stderr,
            )
            sys.exit(1)
        _TELEMETRY_DATABASE_URL = url
    return _TELEMETRY_DATABASE_URL


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_events(
    *,
    database_url: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Query ``telemetry_events`` and return a DataFrame.

    Parameters
    ----------
    database_url :
        PostgreSQL URL.  Defaults to ``TELEMETRY_DATABASE_URL``.
    start, end :
        ISO-8601 datetime filters on ``timestamp`` (inclusive).
    limit :
        Maximum rows to return (for development/testing).
    """
    url = database_url or _get_database_url()
    where_clauses: list[str] = []
    params: list[Any] = []

    if start:
        where_clauses.append("timestamp >= %s")
        params.append(start)
    if end:
        where_clauses.append("timestamp < %s")
        params.append(end)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    limit_sql = ""
    if limit is not None:
        limit_sql = f" LIMIT {limit}"

    query = (
        "SELECT event_id, event_type, timestamp, source, "
        "session_id, schema_version, tags "
        f"FROM public.telemetry_events{where_sql}"
        f"ORDER BY timestamp ASC{limit_sql}"
    )

    with psycopg.connect(url) as conn:
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        return df

    # Normalise columns
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Expand tags into columns for easier metric computation
    if "tags" in df.columns and not df["tags"].isna().all():
        tags_df = pd.json_normalize(df["tags"].apply(lambda x: x if isinstance(x, dict) else {}))
        df = pd.concat([df.drop(columns=["tags"]), tags_df.add_prefix("tag_")], axis=1)
    else:
        df = df.drop(columns=["tags"], errors="ignore")

    return df


# ---------------------------------------------------------------------------
# Metric computations
# ---------------------------------------------------------------------------

ReportData = dict[str, Any]


def compute_metrics(df: pd.DataFrame) -> ReportData:
    """Compute all A1–A11 metrics from a telemetry events DataFrame.

    Returns a dict with keys ``summary``, ``a1`` … ``a11``, and
    ``report_generated_at``.
    """
    report: ReportData = {
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "total_events": len(df),
    }

    if df.empty:
        report["empty"] = True
        return report

    report["empty"] = False
    report["date_range"] = {
        "start": str(df["timestamp"].min()),
        "end": str(df["timestamp"].max()),
    }

    # -- Event type distribution -------------------------------------------
    event_counts = df["event_type"].value_counts()
    report["event_type_distribution"] = event_counts.to_dict()

    # -- A1: Login success rate --------------------------------------------
    login_succeeded = len(df[df["event_type"] == "login_succeeded"])
    login_failed = len(df[df["event_type"] == "login_failed"])
    total_login_attempts = login_succeeded + login_failed
    report["a1"] = {
        "login_succeeded": int(login_succeeded),
        "login_failed": int(login_failed),
        "total_attempts": int(total_login_attempts),
        "success_rate": round(login_succeeded / total_login_attempts, 4)
        if total_login_attempts > 0
        else None,
        "success_rate_pct": round(login_succeeded / total_login_attempts * 100, 1)
        if total_login_attempts > 0
        else None,
    }

    # -- A2: API error rate ------------------------------------------------
    api_total = len(df[df["event_type"] == "api_request_completed"])
    api_errors = len(df[df["event_type"] == "unhandled_api_error"])
    report["a2"] = {
        "api_requests": int(api_total),
        "api_errors": int(api_errors),
        "error_rate_pct": round(api_errors / api_total * 100, 2)
        if api_total > 0
        else None,
    }

    # -- A3: API latency percentiles ---------------------------------------
    api_df = df[df["event_type"] == "api_request_completed"].copy()
    if not api_df.empty and "tag_duration_ms" in api_df.columns:
        dur = api_df["tag_duration_ms"].dropna()
        report["a3"] = {
            "count": int(len(dur)),
            "p50": round(float(dur.quantile(0.50)), 1),
            "p95": round(float(dur.quantile(0.95)), 1),
            "p99": round(float(dur.quantile(0.99)), 1),
            "mean": round(float(dur.mean()), 1),
            "min": round(float(dur.min()), 1),
            "max": round(float(dur.max()), 1),
        }
        # Per-endpoint latency
        if "tag_path" in api_df.columns:
            endpoint_stats = (
                api_df.groupby("tag_path")["tag_duration_ms"]
                .describe(percentiles=[0.5, 0.95, 0.99])
            )
            # describe returns: count, mean, std, min, 25%, 50%, 75%, 95%, 99%, max
            endpoint_latency = endpoint_stats[["count", "mean", "50%", "95%", "99%"]].round(1)
            endpoint_latency.columns = ["count", "mean", "p50", "p95", "p99"]
            endpoint_latency.index.name = "path"
            report["a3_by_endpoint"] = endpoint_latency.reset_index().to_dict(orient="records")
    else:
        report["a3"] = None

    # -- A4: Form validation error rate ------------------------------------
    form_validations = len(df[df["event_type"] == "form_validation_failed"])
    form_opens = len(df[df["event_type"] == "form_opened"])
    report["a4"] = {
        "form_validations_failed": int(form_validations),
        "form_opens": int(form_opens),
        "validation_rate_pct": round(form_validations / form_opens * 100, 2)
        if form_opens > 0
        else None,
    }
    if form_validations > 0:
        form_val_df = df[df["event_type"] == "form_validation_failed"]
        if "tag_form_id" in form_val_df.columns:
            report["a4_by_form"] = (
                form_val_df["tag_form_id"]
                .value_counts()
                .to_dict()
            )

    # -- A5: Section engagement --------------------------------------------
    section_views = df[df["event_type"] == "section_viewed"]
    report["a5"] = {
        "total_section_views": int(len(section_views)),
    }
    if not section_views.empty and "tag_section_id" in section_views.columns:
        report["a5_by_section"] = (
            section_views.groupby("tag_section_id")
            .agg(count=("event_id", "count"))
            .sort_values("count", ascending=False)
            .to_dict(orient="index")
        )

    # -- A6: Form abandonment ----------------------------------------------
    form_abandoned = df[df["event_type"] == "form_abandoned"]
    report["a6"] = {
        "form_abandoned": int(len(form_abandoned)),
        "form_opens": int(form_opens),
        "abandonment_rate_pct": round(len(form_abandoned) / form_opens * 100, 2)
        if form_opens > 0
        else None,
    }

    # -- A7: Account creation rate -----------------------------------------
    report["a7"] = {
        "accounts_created": int(len(df[df["event_type"] == "account_created"])),
    }

    # -- A8: Average cost per unit received --------------------------------
    inbound = df[df["event_type"] == "inbound_order_created"]
    if not inbound.empty:
        has_cost = "tag_unit_cost" in inbound.columns and "tag_quantity" in inbound.columns
        report["a8"] = {
            "total_inbound_orders": int(len(inbound)),
            "has_cost_data": has_cost,
        }
        if has_cost:
            inbound = inbound.dropna(subset=["tag_unit_cost", "tag_quantity"])
            if not inbound.empty:
                inbound["total_cost"] = inbound["tag_quantity"] * inbound["tag_unit_cost"]
                report["a8"]["avg_cost_per_unit"] = round(
                    inbound["total_cost"].sum() / inbound["tag_quantity"].sum(), 2
                )
                report["a8"]["total_cost"] = round(inbound["total_cost"].sum(), 2)
    else:
        report["a8"] = {"total_inbound_orders": 0}

    # -- A9: Stock threshold triggered -------------------------------------
    report["a9"] = {
        "stock_thresholds_triggered": int(
            len(df[df["event_type"] == "stock_threshold_triggered"])
        ),
    }

    # -- A10: Supplier rate variance ---------------------------------------
    supplier_updates = df[df["event_type"] == "supplier_rate_updated"]
    report["a10"] = {
        "supplier_rate_updates": int(len(supplier_updates)),
    }
    if (
        not supplier_updates.empty
        and "tag_old_rate" in supplier_updates.columns
        and "tag_new_rate" in supplier_updates.columns
    ):
        supplier_updates = supplier_updates.dropna(subset=["tag_old_rate", "tag_new_rate"])
        if not supplier_updates.empty:
            supplier_updates["variance_pct"] = (
                abs(supplier_updates["tag_new_rate"] - supplier_updates["tag_old_rate"])
                / supplier_updates["tag_old_rate"]
                * 100
            )
            report["a10"]["avg_variance_pct"] = round(
                supplier_updates["variance_pct"].mean(), 2
            )
            report["a10"]["max_variance_pct"] = round(
                supplier_updates["variance_pct"].max(), 2
            )

    # -- A11: Stale open incidents -----------------------------------------
    report["a11"] = {
        "incident_status_changes": int(
            len(df[df["event_type"] == "incident_status_changed"])
        ),
    }

    return report


# ---------------------------------------------------------------------------
# Dashboard HTML generation
# ---------------------------------------------------------------------------


def _metric_card_html(title: str, value: str, subtitle: str = "") -> str:
    return f"""\
    <div class="card">
      <div class="metric-value">{value}</div>
      <div class="metric-title">{title}</div>
      {f'<div class="metric-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>"""


def _bar_chart_rows(data: dict[str, int | float], max_label_len: int = 30) -> str:
    if not data:
        return "<p class='text-muted'>No data</p>"
    mx = max(data.values()) if data else 1
    rows = ""
    for label, value in sorted(data.items(), key=lambda x: x[1], reverse=True):
        pct = value / mx * 100 if mx else 0
        display_label = label if len(label) <= max_label_len else label[:max_label_len - 3] + "..."
        rows += f"""\
    <div class="bar-row">
      <span class="bar-label" title="{label}">{display_label}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:{pct:.1f}%"></div>
      </div>
      <span class="bar-value">{value}</span>
    </div>"""
    return rows


def generate_dashboard_html(report: ReportData) -> str:
    """Return a self-contained HTML dashboard page."""
    empty = report.get("empty", True)

    def _v(val: Any, suffix: str = "", default: str = "—") -> str:
        if val is None:
            return default
        return f"{val}{suffix}"

    if empty:
        body = "<div class='empty-state'><h2>📊 No hay datos de telemetría</h2><p>Ejecuta el pipeline cuando haya eventos almacenados en Supabase.</p></div>"
    else:
        a1 = report.get("a1", {})
        a2 = report.get("a2", {})
        a3 = report.get("a3")
        a4 = report.get("a4", {})
        a5 = report.get("a5", {})
        a6 = report.get("a6", {})
        a7 = report.get("a7", {})
        a8 = report.get("a8", {})
        a10 = report.get("a10", {})
        a11 = report.get("a11", {})

        sr = _v(a1.get("success_rate_pct"), "%", "N/A")
        er = _v(a2.get("error_rate_pct"), "%", "N/A")
        form_vr = _v(a4.get("validation_rate_pct"), "%", "N/A")
        abandon_r = _v(a6.get("abandonment_rate_pct"), "%", "N/A")
        total = report.get("total_events", 0)
        dr = report.get("date_range", {})

        a3_section = ""
        if a3:
            a3_section = f"""\
    <div class="section">
      <h2>A3 — Latencia de API</h2>
      <div class="card-grid-4">
        {_metric_card_html("P50", _v(a3.get("p50"), " ms", "N/A"))}
        {_metric_card_html("P95", _v(a3.get("p95"), " ms", "N/A"))}
        {_metric_card_html("P99", _v(a3.get("p99"), " ms", "N/A"))}
        {_metric_card_html("Media", _v(a3.get("mean"), " ms", "N/A"))}
      </div>
      <p class="text-muted">Basado en {a3.get("count", 0)} peticiones · Min {_v(a3.get("min"), " ms")} · Max {_v(a3.get("max"), " ms")}</p>
    </div>"""

            if report.get("a3_by_endpoint"):
                rows = ""
                for ep in report["a3_by_endpoint"]:
                    rows += f"""\
    <tr>
      <td class="cell-mono">{ep.get("path", "?")}</td>
      <td class="cell-num">{ep.get("count", 0)}</td>
      <td class="cell-num">{ep.get("mean", "—")}</td>
      <td class="cell-num">{ep.get("p50", "—")}</td>
      <td class="cell-num">{ep.get("p95", "—")}</td>
      <td class="cell-num">{ep.get("p99", "—")}</td>
    </tr>"""
                a3_section += f"""\
    <div class="section">
      <h3>Latencia por endpoint</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Endpoint</th><th>#</th><th>Media</th><th>P50</th><th>P95</th><th>P99</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""

        a4_section = ""
        if report.get("a4_by_form"):
            a4_section = f"""\
    <div class="section">
      <h3>Validaciones fallidas por formulario</h3>
      <div class="bar-chart">{_bar_chart_rows(report["a4_by_form"])}</div>
    </div>"""

        event_dist_section = ""
        if report.get("event_type_distribution"):
            event_dist_section = f"""\
    <div class="section">
      <h2>Distribución de eventos</h2>
      <div class="bar-chart">{_bar_chart_rows(report["event_type_distribution"])}</div>
    </div>"""

        a5_section = ""
        if report.get("a5_by_section"):
            rows = ""
            for section_id, vals in report["a5_by_section"].items():
                rows += f"""\
    <tr>
      <td class="cell-mono">{section_id}</td>
      <td class="cell-num">{vals.get("count", 0)}</td>
    </tr>"""
            a5_section = f"""\
    <div class="section">
      <h2>A5 — Engagement por sección</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Sección</th><th>Visitas</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""

        body = f"""\
    <div class="summary-bar">
      <span><strong>{total}</strong> eventos</span>
      <span>Desde {dr.get("start", "?")[:19]} hasta {dr.get("end", "?")[:19]}</span>
      <span>Generado {report.get("report_generated_at", "")[:19]}</span>
    </div>

    <!-- Tarjetas resumen -->
    <div class="section">
      <h2>Resumen de métricas</h2>
      <div class="card-grid-4">
        {_metric_card_html("A1 — Logins exitosos", _v(a1.get("login_succeeded"), "", "0"), f"Fallidos: {a1.get('login_failed', 0)} · Tasa: {sr}")}
        {_metric_card_html("A2 — Error API", er, f"Errores: {a2.get('api_errors', 0)} / {a2.get('api_requests', 0)}")}
        {_metric_card_html("A4 — Validación formularios", form_vr, f"Fallos: {a4.get('form_validations_failed', 0)} / {a4.get('form_opens', 0)}")}
        {_metric_card_html("A6 — Abandono formularios", abandon_r, f"Abandonos: {a6.get('form_abandoned', 0)}")}
      </div>
      <div class="card-grid-4">
        {_metric_card_html("A5 — Secciones visitadas", str(a5.get("total_section_views", 0)))}
        {_metric_card_html("A7 — Cuentas creadas", str(a7.get("accounts_created", 0)))}
        {_metric_card_html("A10 — Actualizaciones proveedor", str(a10.get("supplier_rate_updates", 0)), f"Var. media: {_v(a10.get('avg_variance_pct'), '%', '—')}")}
        {_metric_card_html("A11 — Cambios incidencia", str(a11.get("incident_status_changes", 0)))}
      </div>
    </div>

    {event_dist_section}

    {a3_section}

    {a4_section}

    {a5_section}

    <!-- A8: Costes inbound -->
    <div class="section">
      <h2>A8 — Coste medio por unidad recibida</h2>
      <div class="card-grid-4">
        {_metric_card_html("Órdenes inbound", str(a8.get("total_inbound_orders", 0)))}
        {_metric_card_html("Coste total", _v(a8.get("total_cost"), " €", "N/A"), "Sin datos de unit_cost" if not a8.get("has_cost_data") else "")}
        {_metric_card_html("Coste medio/unidad", _v(a8.get("avg_cost_per_unit"), " €", "N/A"))}
      </div>
    </div>"""

    return f"""\
<!doctype html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Informe de Telemetría | Nexova</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
           background: #f8f9fa; color: #1f2328; line-height: 1.5; }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 16px; }}
    header {{ background: #1f2328; color: #fff; padding: 20px 0; }}
    header h1 {{ font-size: 1.5rem; font-weight: 700; }}
    header .sub {{ color: #9ca3af; font-size: 0.875rem; margin-top: 4px; }}
    .summary-bar {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
                    padding: 12px 20px; margin-bottom: 24px; display: flex; gap: 24px;
                    flex-wrap: wrap; font-size: 0.875rem; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ font-size: 1.25rem; font-weight: 600; margin-bottom: 12px;
                   padding-bottom: 8px; border-bottom: 2px solid #f97316; }}
    .section h3 {{ font-size: 1rem; font-weight: 600; margin: 16px 0 8px; color: #4b5563; }}
    .card-grid-4 {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 12px; margin-bottom: 16px; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
             padding: 16px; }}
    .metric-value {{ font-size: 1.75rem; font-weight: 700; color: #f97316; }}
    .metric-title {{ font-size: 0.8rem; color: #6b7280; margin-top: 4px; }}
    .metric-subtitle {{ font-size: 0.75rem; color: #9ca3af; margin-top: 2px; }}
    .empty-state {{ text-align: center; padding: 80px 20px; }}
    .empty-state h2 {{ font-size: 1.5rem; color: #6b7280; margin-bottom: 8px; }}
    .text-muted {{ color: #6b7280; font-size: 0.8rem; margin-top: 4px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
    th {{ background: #f3f4f6; font-weight: 600; color: #374151; }}
    .cell-mono {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.75rem; }}
    .cell-num {{ text-align: right; font-family: 'SF Mono', 'Fira Code', monospace; }}
    .bar-chart {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px;
                  padding: 12px; }}
    .bar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
    .bar-label {{ flex: 0 0 200px; font-size: 0.78rem; white-space: nowrap;
                  overflow: hidden; text-overflow: ellipsis; }}
    .bar-track {{ flex: 1; height: 20px; background: #f3f4f6; border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: #f97316; border-radius: 4px;
                 transition: width 0.3s; min-width: 2px; }}
    .bar-value {{ flex: 0 0 50px; text-align: right; font-size: 0.78rem;
                  font-weight: 600; color: #374151; }}
    footer {{ text-align: center; padding: 24px; color: #9ca3af; font-size: 0.75rem; }}
  </style>
</head>
<body>
  <header>
    <div class="container">
      <h1>📊 Informe de Telemetría · Nexova</h1>
      <div class="sub">Pipeline Pandas — Métricas A1–A11</div>
    </div>
  </header>
  <main class="container">
    {body}
  </main>
  <footer>Generado por el pipeline de analítica de telemetría · {report.get("report_generated_at", "")[:19]}</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_report(
    *,
    database_url: str | None = None,
    start: str | None = None,
    end: str | None = None,
    limit: int | None = None,
) -> ReportData:
    """Load events, compute metrics, return report data."""
    df = load_events(database_url=database_url, start=start, end=end, limit=limit)
    return compute_metrics(df)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Nexova Telemetry Analytics — Pandas pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python -m app.telemetry.report\n"
            "  python -m app.telemetry.report --start 2026-11-01 --end 2026-11-07\n"
            "  python -m app.telemetry.report --limit 1000 --output reporte.html\n"
        ),
    )
    parser.add_argument(
        "--start",
        help="Filtrar eventos desde (ISO-8601, ej. 2026-11-01)",
    )
    parser.add_argument(
        "--end",
        help="Filtrar eventos hasta (ISO-8601, ej. 2026-11-07)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Máximo de eventos a cargar (para pruebas)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Ruta del archivo HTML de salida (por defecto: telemetry-dashboard.html)",
    )
    args = parser.parse_args(argv)

    print("📡 Cargando eventos de telemetría desde Supabase…")
    report = build_report(
        start=args.start,
        end=args.end,
        limit=args.limit,
    )

    if report.get("empty"):
        print("⚠️  No hay eventos en el período seleccionado.")
        if args.output:
            html = generate_dashboard_html(report)
            Path(args.output).write_text(html, encoding="utf-8")
            print(f"📄 Dashboard generado: {args.output}")
        return 0

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  📊 INFORME DE TELEMETRÍA")
    print(f"  Total eventos: {report['total_events']}")
    print(f"  Período: {report['date_range']['start'][:19]} — {report['date_range']['end'][:19]}")
    print(f"{'=' * 50}")

    a1 = report.get("a1", {})
    print(f"\nA1 — Tasa de éxito de login: {a1.get('success_rate_pct', 'N/A')}%")
    print(f"     Exitosos: {a1.get('login_succeeded', 0)} · Fallidos: {a1.get('login_failed', 0)}")

    a2 = report.get("a2", {})
    print(f"\nA2 — Tasa de error de API: {a2.get('error_rate_pct', 'N/A')}%")
    print(f"     Errores: {a2.get('api_errors', 0)} / {a2.get('api_requests', 0)}")

    if report.get("a3"):
        a3 = report["a3"]
        print(f"\nA3 — Latencia de API: P50={a3.get('p50', 'N/A')}ms P95={a3.get('p95', 'N/A')}ms P99={a3.get('p99', 'N/A')}ms")

    a4 = report.get("a4", {})
    print(f"\nA4 — Validación formularios: {a4.get('validation_rate_pct', 'N/A')}%")

    a6 = report.get("a6", {})
    print(f"\nA6 — Abandono formularios: {a6.get('abandonment_rate_pct', 'N/A')}%")

    a7 = report.get("a7", {})
    print(f"\nA7 — Cuentas creadas: {a7.get('accounts_created', 0)}")

    a10 = report.get("a10", {})
    print(f"\nA10 — Actualizaciones proveedor: {a10.get('supplier_rate_updates', 0)}")

    # Generate dashboard HTML
    output_path = args.output or "telemetry-dashboard.html"
    html = generate_dashboard_html(report)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"\n📄 Dashboard generado: {output_path}")
    print("✅ Listo.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
