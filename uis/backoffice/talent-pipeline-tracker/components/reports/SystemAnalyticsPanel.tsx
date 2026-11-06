"use client";

import { useCallback, useEffect, useState } from "react";
import { Spinner } from "@/components/ui";
import {
  getTelemetryReport,
  TelemetryReportError,
} from "@/lib/telemetry-report-client";
import type {
  TelemetryA1,
  TelemetryA2,
  TelemetryA3,
  TelemetryA4,
  TelemetryA5BySection,
  TelemetryA8,
  TelemetryA10,
  TelemetryEndpointLatency,
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
// Data shaping helpers
// ---------------------------------------------------------------------------

function percentage(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

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

  if (!report || report.empty) {
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

  const a1 = report.a1 ?? ({} as TelemetryA1);
  const a2 = report.a2 ?? ({} as TelemetryA2);
  const a3 = report.a3 ?? null;
  const a4 = report.a4 ?? ({} as TelemetryA4);
  const a8 = report.a8 ?? ({} as TelemetryA8);
  const a10 = report.a10 ?? ({} as TelemetryA10);

  const eventTypeBars: { label: string; value: number }[] = Object.entries(
    report.event_type_distribution ?? {},
  )
    .map(([label, value]) => ({ label, value: Number(value) }))
    .sort((x, y) => y.value - x.value);

  const a5Sections: { label: string; value: number }[] = Object.entries(
    report.a5_by_section ?? ({} as TelemetryA5BySection),
  )
    .map(([label, entry]) => ({ label, value: entry.count }))
    .sort((x, y) => y.value - x.value);

  const a4Forms: { label: string; value: number }[] = Object.entries(
    report.a4_by_form ?? {},
  )
    .map(([label, value]) => ({ label, value: Number(value) }))
    .sort((x, y) => y.value - x.value);

  const endpointRows: (string | number)[][] = (report.a3_by_endpoint ?? []).map(
    (e: TelemetryEndpointLatency) => [
      e.path,
      e.count,
      e.mean,
      e.p50,
      e.p95,
      e.p99,
    ],
  );

  const a5Total = report.a5?.total_section_views ?? 0;

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
            {report.total_events} events · generated{" "}
            {new Date(report.report_generated_at).toLocaleString()}
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
        <MetricCard label="Total events" value={report.total_events} />
        <MetricCard label="Login success" value={percentage(a1.success_rate_pct)} tone={a1.success_rate_pct !== null && a1.success_rate_pct < 90 ? "warn" : "good"} />
        <MetricCard label="API error rate" value={percentage(a2.error_rate_pct)} tone={a2.error_rate_pct !== null && a2.error_rate_pct > 5 ? "warn" : "good"} />
        <MetricCard label="Accounts created" value={report.a7?.accounts_created ?? 0} />
        <MetricCard label="Stock alerts" value={report.a9?.stock_thresholds_triggered ?? 0} />
      </div>

      {/* Login + API errors */}
      <SectionHeading>Authentication &amp; API health</SectionHeading>
      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <MetricCard label="Successful logins" value={a1.login_succeeded ?? 0} subtitle={`${a1.total_attempts ?? 0} total attempts`} />
        <MetricCard label="Failed logins" value={a1.login_failed ?? 0} />
        <div className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
          <h3 className="text-sm font-bold uppercase tracking-[0.12em] text-brand-anthracite/70">
            API latency (ms)
          </h3>
          {a3 ? (
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div><p className="text-xs text-brand-anthracite/55">p50</p><p className="text-lg font-black tabular-nums">{a3.p50}</p></div>
              <div><p className="text-xs text-brand-anthracite/55">p95</p><p className="text-lg font-black tabular-nums">{a3.p95}</p></div>
              <div><p className="text-xs text-brand-anthracite/55">p99</p><p className="text-lg font-black tabular-nums">{a3.p99}</p></div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-brand-anthracite/50">No latency data.</p>
          )}
        </div>
      </div>

      {/* Event distribution */}
      <SectionHeading>Event distribution</SectionHeading>
      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <BarChart title="Events by type" data={eventTypeBars} />
        <BarChart title="Section views" data={a5Sections} formatValue={(v) => `${v}`} color="bg-brand-anthracite" />
      </div>

      {/* Forms */}
      <SectionHeading>Forms</SectionHeading>
      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        <MetricCard label="Form validation failures" value={a4.form_validations_failed ?? 0} subtitle={`${a4.form_opens ?? 0} form opens`} />
        <MetricCard label="Form abandonment rate" value={percentage(report.a6?.abandonment_rate_pct)} />
        <BarChart title="Failures by form" data={a4Forms} />
      </div>

      {/* Endpoint latency table */}
      <SectionHeading>Per-endpoint latency</SectionHeading>
      <div className="mt-4">
        <DataTable
          title="Latency by endpoint (ms)"
          headers={["Endpoint", "Count", "Mean", "p50", "p95", "p99"]}
          rows={endpointRows}
        />
      </div>

      {/* Operational */}
      <SectionHeading>Operations</SectionHeading>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Inbound orders" value={a8.total_inbound_orders ?? 0} />
        <MetricCard label="Avg cost / unit" value={a8.avg_cost_per_unit !== undefined ? `$${a8.avg_cost_per_unit.toFixed(2)}` : "—"} />
        <MetricCard label="Supplier rate updates" value={a10.supplier_rate_updates ?? 0} />
        <MetricCard label="Incident status changes" value={report.a11?.incident_status_changes ?? 0} />
      </div>

      <p className="mt-8 text-xs text-brand-anthracite/50">
        Metrics A1–A11 computed from instrumented frontend telemetry events.
      </p>
    </div>
  );
}

