"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Button, Spinner } from "@/components/ui";
import { getWeeklyBusinessPerformance } from "@/lib/business-reporting";
import { NexovaApiError, nexovaApi } from "@/lib/nexova-api";
import type { WeeklyBusinessPerformance } from "@/types/business-reporting";

function formatMaterialCost(amount: number | string, currency: "EUR" | "USD"): string {
  const value = typeof amount === "number" ? amount : Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function errorMessage(error: unknown): string {
  if (error instanceof NexovaApiError) {
    if (error.kind === "http" && error.status === 404) {
      return "No hay resultados de reporting para la semana seleccionada.";
    }
    if (error.kind === "http" && error.status === 401) {
      return "Tu sesión no está autorizada. Inicia sesión de nuevo para consultar este informe.";
    }
    if (error.kind === "http" && error.status === 403) {
      return "No tienes permiso para consultar este informe.";
    }
    return error.message;
  }
  return "No se pudieron cargar los datos de Business Analysis.";
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail?: string }) {
  return (
    <div className="rounded-xl bg-brand-lightgray/35 p-4">
      <p className="text-xs font-bold uppercase tracking-[0.1em] text-brand-anthracite/60">{label}</p>
      <p className="mt-2 text-2xl font-black tracking-tight text-brand-anthracite">{value}</p>
      {detail && <p className="mt-1 text-xs text-brand-anthracite/60">{detail}</p>}
    </div>
  );
}

function PerformanceCard({ row }: { row: WeeklyBusinessPerformance }) {
  const officeTone = row.office === "Valencia"
    ? "border-l-4 border-l-brand-orange"
    : "border-l-4 border-l-sky-600";

  return (
    <article className={`rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:p-6 ${officeTone}`}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-brand-anthracite/55">{row.office}</p>
          <h2 className="mt-1 break-all text-lg font-black">{row.programme_id}</h2>
        </div>
        <p className="rounded-full bg-brand-lightgray/50 px-3 py-1 text-sm font-semibold">
          Semana desde {row.week_start}
        </p>
      </header>

      <dl className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total material cost" value={formatMaterialCost(row.total_material_cost, row.currency)} detail={`Moneda: ${row.currency}`} />
        <Metric label="Kits delivered" value={row.kits_delivered_count} detail="Eventos outbound válidos" />
        <Metric label="Shortage events" value={row.shortage_events_count} />
        <Metric label="Cost variance events" value={row.cost_variance_events_count} />
      </dl>
    </article>
  );
}

export default function BusinessAnalysisPage() {
  const [rows, setRows] = useState<WeeklyBusinessPerformance[]>([]);
  const [weekStart, setWeekStart] = useState("");
  const [appliedWeek, setAppliedWeek] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async (week: string, signal: { active: boolean }) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWeeklyBusinessPerformance(nexovaApi, week ? { week_start: week } : {});
      if (!signal.active) return;
      setRows(data);
      setAppliedWeek(week);
    } catch (failure) {
      if (!signal.active) return;
      setRows([]);
      setError(errorMessage(failure));
    } finally {
      if (signal.active) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const signal = { active: true };
    queueMicrotask(() => {
      if (signal.active) void loadReport("", signal);
    });
    return () => { signal.active = false; };
  }, [loadReport]);

  function submitFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadReport(weekStart, { active: true });
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-5 border-b border-brand-lightgray pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange-dark">Reports</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Business Analysis</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-brand-anthracite/70">
            Informe de rendimiento semanal por oficina y programa, calculado por el pipeline de reporting.
          </p>
        </div>
        <form onSubmit={submitFilter} className="flex flex-col gap-2 sm:min-w-72">
          <label htmlFor="week-start" className="text-xs font-bold uppercase tracking-[0.1em] text-brand-anthracite/65">
            Filtrar por semana ISO (lunes)
          </label>
          <div className="flex flex-wrap gap-2">
            <input
              id="week-start"
              type="date"
              value={weekStart}
              onChange={(event) => setWeekStart(event.target.value)}
              className="min-h-11 min-w-0 flex-1 rounded-lg border border-brand-lightgray bg-brand-white px-3 text-sm focus-visible:outline-2 focus-visible:outline-brand-orange"
            />
            <Button type="submit" disabled={loading}>Apply</Button>
          </div>
          <p className="text-xs text-brand-anthracite/55">
            {appliedWeek ? `Semana seleccionada: ${appliedWeek}` : "Sin filtro: resultados disponibles más recientes."}
          </p>
        </form>
      </header>

      <section className="mt-7 space-y-4" aria-label="Weekly business performance" aria-live="polite">
        {loading ? (
          <div className="flex min-h-48 items-center justify-center gap-3 rounded-2xl border border-brand-lightgray bg-brand-white p-8">
            <Spinner size="sm" />
            <p className="text-sm text-brand-anthracite/70">Cargando resultados de reporting…</p>
          </div>
        ) : error ? (
          <div role="alert" className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-800">
            <p className="font-bold">No se pudo cargar Business Analysis</p>
            <p className="mt-1">{error}</p>
          </div>
        ) : rows.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-brand-lightgray bg-brand-white p-8 text-center">
            <h2 className="text-lg font-bold">No hay resultados disponibles</h2>
            <p className="mt-2 text-sm text-brand-anthracite/65">
              {appliedWeek ? `La API no devolvió resultados para la semana ${appliedWeek}.` : "La API todavía no ha devuelto resultados semanales de negocio."}
            </p>
          </div>
        ) : (
          <>
            <p className="text-sm text-brand-anthracite/65">
              {rows.length} {rows.length === 1 ? "resultado" : "resultados"} devueltos por la API. Los importes se mantienen separados por moneda.
            </p>
            {rows.map((row) => (
              <PerformanceCard
                key={`${row.week_start}:${row.office}:${row.programme_id}`}
                row={row}
              />
            ))}
          </>
        )}
      </section>
    </main>
  );
}