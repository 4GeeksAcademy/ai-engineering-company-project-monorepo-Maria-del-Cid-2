"use client";

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/ui";
import {
  getTelemetryReport,
  TelemetryReportError,
} from "@/lib/telemetry-report-client";
import type {
  TelemetryLoginRateRow,
  TelemetryApiErrorRow,
  TelemetryLatencyRow,
  TelemetryFormValidationRow,
  TelemetrySectionEngagementRow,
  TelemetryReport,
} from "@/types/reports";

// ---------------------------------------------------------------------------
// Small presentational helpers (CSS-only charts)
// ---------------------------------------------------------------------------

function MetricCard({
  label,
  value,
  subtitle,
  tone = "default",
}: {
  label: string;
  value: string | number;
  subtitle?: string;
  tone?: "default" | "good" | "warn";
}) {
  const toneClass =
    tone === "good"
      ? "text-green-700"
      : tone === "warn"
        ? "text-amber-700"
        : "text-brand-anthracite";
  return (
    <div className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-brand-anthracite/55">
        {label}
      </p>
      <p className={`mt-2 text-3xl font-black tracking-tight ${toneClass}`}>
        {value}
      </p>
      {subtitle && (
        <p className="mt-1 text-xs text-brand-anthracite/60">{subtitle}</p>
      )}
    </div>
  );
}

function BarChart({
  title,
  data,
  formatValue = (v) => String(v),
  color = "bg-brand-orange",
}: {
  title: string;
  data: { label: string; value: number }[];
  formatValue?: (value: number) => string;
  color?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <section className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-brand-anthracite/70">
        {title}
      </h3>
      {data.length === 0 ? (
        <p className="mt-4 text-sm text-brand-anthracite/50">No data yet.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {data.map((d) => (
            <div key={d.label}>
              <div className="mb-1 flex items-center justify-between text-xs text-brand-anthracite/70">
                <span className="truncate pr-3">{d.label}</span>
                <span className="font-semibold tabular-nums">
                  {formatValue(d.value)}
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-brand-lightgray">
                <div
                  className={`h-full rounded-full ${color}`}
                  style={{ width: `${(d.value / max) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DataTable({
  title,
  headers,
  rows,
}: {
  title: string;
  headers: string[];
  rows: (string | number)[][];
}) {
  return (
    <section className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-brand-anthracite/70">
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-brand-anthracite/50">No data yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-brand-lightgray text-xs font-bold uppercase tracking-[0.1em] text-brand-anthracite/60">
                {headers.map((h) => (
                  <th key={h} className="px-3 py-2">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-brand-lightgray/60 last:border-0">
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={`px-3 py-2 tabular-nums ${j === 0 ? "font-semibold text-brand-anthracite" : "text-brand-anthracite/75"}`}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function SectionHeading({ children }: { children: string }) {
  return (
    <h2 className="mt-8 border-b border-brand-lightgray pb-2 text-lg font-black tracking-tight text-brand-anthracite">
      {children}
    </h2>
  );
}

// ---------------------------------------------------------------------------
// Data shaping helpers (empty — all shaping done inline with the new API)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------

export function SystemAnalyticsPanel() {
  const [report, setReport] = useState<TelemetryReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await getTelemetryReport());
    } catch (requestError) {
      if (requestError instanceof TelemetryReportError) {
        setError(requestError.message);
      } else {
        setError("Unable to load the telemetry report.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="mx-auto flex max-w-7xl items-center justify-center px-4 py-24">
        <Spinner className="h-8 w-8" />
        <span className="ml-3 text-sm text-brand-anthracite/60">
          Loading analytics…
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12">
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="mt-4 rounded-lg bg-brand-orange px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-orange-dark"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12">
        <div className="rounded-2xl border border-brand-lightgray bg-brand-white p-8 text-center shadow-sm">
          <h1 className="text-xl font-black tracking-tight">System Analytics</h1>
          <p className="mt-3 text-brand-anthracite/70">
            No telemetry events recorded yet. Events will appear here as users
            interact with the application.
          </p>
        </div>
      </div>
    );
  }

  const { period, metrics } = report;

  // Derive summary aggregates from the grouped metric rows
  const a1Data = metrics.a1 as TelemetryLoginRateRow[];
  const totalLoginAttempts = a1Data.reduce((s, r) => s + r.total_attempts, 0);
  const totalLoginSucceeded = a1Data.reduce((s, r) => s + r.login_succeeded, 0);
  const totalLoginFailed = a1Data.reduce((s, r) => s + r.login_failed, 0);
  const overallLoginSuccessPct =
    totalLoginAttempts > 0
      ? (totalLoginSucceeded / totalLoginAttempts) * 100
      : null;

  const a2Data = metrics.a2 as TelemetryApiErrorRow[];
  const totalApiRequests = a2Data.reduce((s, r) => s + r.total_requests, 0);
  const totalApiErrors = a2Data.reduce((s, r) => s + r.errors, 0);
  const overallApiErrorPct =
    totalApiRequests > 0 ? (totalApiErrors / totalApiRequests) * 100 : null;

  const a3Data = metrics.a3 as TelemetryLatencyRow[];

  const a4Data = metrics.a4 as TelemetryFormValidationRow[];
  const totalFormOpens = a4Data.reduce((s, r) => s + r.form_opens, 0);
  const totalFormFailures = a4Data.reduce((s, r) => s + r.validation_failures, 0);

  const a5Data = metrics.a5 as TelemetrySectionEngagementRow[];
  const totalSectionViews = a5Data.reduce((s, r) => s + r.views, 0);

  // Data for charts
  const eventTypeBars: { label: string; value: number }[] = [
    { label: "Login attempts", value: totalLoginAttempts },
    { label: "API requests", value: totalApiRequests },
    { label: "API errors", value: totalApiErrors },
    { label: "Form errors", value: totalFormFailures },
    { label: "Section views", value: totalSectionViews },
  ].filter((d) => d.value > 0);

  const a5Sections: { label: string; value: number }[] = a5Data.map((r) => ({
    label: r.dimension_value,
    value: r.views,
  }));

  const a4Forms: { label: string; value: number }[] = a4Data.map((r) => ({
    label: r.dimension_value,
    value: r.validation_failures,
  }));

  const endpointRows: (string | number)[][] = a3Data.map(
    (e: TelemetryLatencyRow) => [
      e.dimension_value,
      e.count,
      e.mean,
      e.p50,
      e.p95,
      e.p99,
    ],
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange-dark">
            Reports
          </p>
          <h1 className="mt-1 text-2xl font-black tracking-tight text-brand-anthracite">
            System Analytics
          </h1>
          <p className="mt-1 text-sm text-brand-anthracite/60">
            {period.days} day period ending {new Date(period.end).toLocaleDateString()} ·{" "}
            {totalLoginAttempts + totalApiRequests + totalFormFailures + totalSectionViews} events
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-brand-lightgray bg-brand-white px-4 py-2 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/40"
        >
          Refresh
        </button>
      </header>

      {/* Summary metric cards */}
      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard label="Period" value={`${period.days}d`} subtitle={`${period.start.slice(0, 10)} → ${period.end.slice(0, 10)}`} />
        <MetricCard label="Login success" value={overallLoginSuccessPct !== null ? `${overallLoginSuccessPct.toFixed(1)}%` : "—"} tone={overallLoginSuccessPct !== null && overallLoginSuccessPct < 90 ? "warn" : "good"} />
        <MetricCard label="API error rate" value={overallApiErrorPct !== null ? `${overallApiErrorPct.toFixed(1)}%` : "—"} tone={overallApiErrorPct !== null && overallApiErrorPct > 5 ? "warn" : "good"} />
        <MetricCard label="Form opens" value={totalFormOpens} />
        <MetricCard label="Section views" value={totalSectionViews} />
      </div>

      {/* Authentication & API health */}
      <SectionHeading>Authentication &amp; API health</SectionHeading>
      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Successful logins"
          value={totalLoginSucceeded}
          subtitle="succeeded"
          tone="good"
        />
        <MetricCard label="Failed logins" value={totalLoginFailed} tone="warn" />
        <MetricCard
          label="Login success rate"
          value={overallLoginSuccessPct !== null ? `${overallLoginSuccessPct.toFixed(1)}%` : "—"}
          subtitle={`${totalLoginAttempts} total attempts`}
        />
        <MetricCard
          label="API error rate"
          value={overallApiErrorPct !== null ? `${overallApiErrorPct.toFixed(1)}%` : "—"}
          subtitle={`${totalApiErrors} of ${totalApiRequests} requests`}
          tone={overallApiErrorPct !== null && overallApiErrorPct > 5 ? "warn" : "good"}
        />
      </div>
      <div className="mt-4 max-h-[26rem] overflow-y-auto rounded-2xl border border-brand-lightgray bg-brand-white shadow-sm">
        <DataTable
          title="API latency by endpoint (ms)"
          headers={["Endpoint", "Count", "Mean", "p50", "p95", "p99"]}
          rows={endpointRows}
        />
      </div>

      {/* Event distribution */}
      {eventTypeBars.length > 0 && (
        <>
          <SectionHeading>Event distribution</SectionHeading>
          <div className="mt-4 grid gap-6 lg:grid-cols-2">
            <BarChart title="Events by type" data={eventTypeBars} />
            <BarChart title="Section views" data={a5Sections} formatValue={(v) => `${v}`} color="bg-brand-anthracite" />
          </div>
        </>
      )}

      {/* Forms */}
      <SectionHeading>Forms</SectionHeading>
      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <MetricCard label="Form validation failures" value={totalFormFailures} subtitle={`${totalFormOpens} form opens`} />
        <BarChart title="Failures by form" data={a4Forms} />
      </div>

      {/* Login success by day table */}
      {a1Data.length > 0 && (
        <>
          <SectionHeading>Login success by day</SectionHeading>
          <div className="mt-4">
            <DataTable
              title="Daily login rate"
              headers={["Date", "Succeeded", "Failed", "Total", "Success rate"]}
              rows={a1Data.map((r) => [
                r.dimension_value,
                r.login_succeeded,
                r.login_failed,
                r.total_attempts,
                `${r.success_rate_pct}%`,
              ])}
            />
          </div>
        </>
      )}

      {/* API error rate by endpoint table */}
      {a2Data.length > 0 && (
        <>
          <SectionHeading>API error rate by endpoint</SectionHeading>
          <div className="mt-4">
            <DataTable
              title="Errors by endpoint"
              headers={["Endpoint", "Requests", "Errors", "Error rate"]}
              rows={a2Data.map((r) => [
                r.dimension_value,
                r.total_requests,
                r.errors,
                `${r.error_rate_pct}%`,
              ])}
            />
          </div>
        </>
      )}

      <p className="mt-8 text-xs text-brand-anthracite/50">
        Metrics A1–A5 computed from instrumented frontend telemetry events.
        Each metric is grouped by dimension and fully serializable to JSON.
      </p>
    </div>
  );
}

