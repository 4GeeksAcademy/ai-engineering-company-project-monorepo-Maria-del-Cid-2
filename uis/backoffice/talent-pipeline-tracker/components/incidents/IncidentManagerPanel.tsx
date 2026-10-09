"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Input, Select, Spinner, Textarea } from "@/components/ui";
import {
  createIncident,
  getIncidentErrorMessage,
  getIncidentFieldError,
  getIncidentSummary,
  listIncidents,
  updateIncidentStatus,
} from "@/lib/incidents-api";
import {
  INCIDENT_MANAGER_BRANCHES,
  INCIDENT_MANAGER_BRANCH_LABELS,
  INCIDENT_MANAGER_CATEGORIES,
  INCIDENT_MANAGER_CATEGORY_LABELS,
  INCIDENT_MANAGER_ORIGINS,
  INCIDENT_MANAGER_ORIGIN_LABELS,
  INCIDENT_MANAGER_STATUSES,
  INCIDENT_MANAGER_STATUS_LABELS,
  INCIDENT_MANAGER_TRANSITIONS,
  type Incident,
  type IncidentCreatePayload,
  type IncidentManagerBranch,
  type IncidentManagerCategory,
  type IncidentManagerOrigin,
  type IncidentManagerStatus,
  type IncidentSummary,
} from "@/types/incident-manager";

const categoryOptions = INCIDENT_MANAGER_CATEGORIES.map((value) => ({
  value,
  label: INCIDENT_MANAGER_CATEGORY_LABELS[value],
}));
const statusOptions = INCIDENT_MANAGER_STATUSES.map((value) => ({
  value,
  label: INCIDENT_MANAGER_STATUS_LABELS[value],
}));
const originOptions = INCIDENT_MANAGER_ORIGINS.map((value) => ({
  value,
  label: INCIDENT_MANAGER_ORIGIN_LABELS[value],
}));
const branchOptions = INCIDENT_MANAGER_BRANCHES.map((value) => ({
  value,
  label: INCIDENT_MANAGER_BRANCH_LABELS[value],
}));

function apiErrorMessage(error: unknown): string {
  return getIncidentErrorMessage(error);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function SummaryCard({ label, value, tone = "default" }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-brand-anthracite/55">{label}</p>
      <p className={`mt-2 text-3xl font-black tracking-tight ${tone}`}>{value}</p>
    </div>
  );
}

function IncidentForm({ onCreated }: { onCreated: (incident: Incident) => void }) {
  const [form, setForm] = useState<IncidentCreatePayload>({
    title: "",
    description: "",
    category: "other",
    status: "open",
    origin: "internal",
    branch: "central",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [field, setField] = useState<string | null>(null);

  function updateField<K extends keyof IncidentCreatePayload>(key: K, value: IncidentCreatePayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setField(null);
    try {
      onCreated(await createIncident(form));
      setForm((current) => ({ ...current, title: "", description: "" }));
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
      setField(getIncidentFieldError(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:p-6">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">New record</p>
      <h2 className="mt-1 text-xl font-black tracking-tight">Register incident</h2>
      <form className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" onSubmit={submit}>
        <Input label="Title" required maxLength={120} value={form.title} error={field === "title" ? error ?? undefined : undefined} onChange={(event) => updateField("title", event.target.value)} />
        <Select label="Category" options={categoryOptions} value={form.category} error={field === "category" ? error ?? undefined : undefined} onChange={(event) => updateField("category", event.target.value as IncidentManagerCategory)} />
        <Select label="Origin" options={originOptions} value={form.origin} error={field === "origin" ? error ?? undefined : undefined} onChange={(event) => updateField("origin", event.target.value as IncidentManagerOrigin)} />
        <Select label="Branch" options={branchOptions} value={form.branch} error={field === "branch" ? error ?? undefined : undefined} onChange={(event) => updateField("branch", event.target.value as IncidentManagerBranch)} />
        <Select label="Initial status" options={statusOptions} value={form.status} error={field === "status" ? error ?? undefined : undefined} onChange={(event) => updateField("status", event.target.value as IncidentManagerStatus)} />
        <Textarea label="Description" required className="sm:col-span-2 lg:col-span-3" value={form.description} error={field === "description" ? error ?? undefined : undefined} onChange={(event) => updateField("description", event.target.value)} />
        {error && !field && <p role="alert" className="text-sm text-red-700 sm:col-span-2 lg:col-span-3">{error}</p>}
        <div className="sm:col-span-2 lg:col-span-3"><Button type="submit" loading={saving}>Create incident</Button></div>
      </form>
    </section>
  );
}

function IncidentRow({ incident, onUpdated }: { incident: Incident; onUpdated: (incident: Incident) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextStatuses = INCIDENT_MANAGER_TRANSITIONS[incident.status];

  async function changeStatus(status: IncidentManagerStatus) {
    setBusy(true);
    setError(null);
    try {
      onUpdated(await updateIncidentStatus(incident.id, status));
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{incident.title}</h3>
            <Badge className="bg-nexova-100 text-nexova-800">{INCIDENT_MANAGER_STATUS_LABELS[incident.status]}</Badge>
          </div>
          <p className="mt-1 text-sm text-brand-anthracite/65">{INCIDENT_MANAGER_CATEGORY_LABELS[incident.category]} · {INCIDENT_MANAGER_ORIGIN_LABELS[incident.origin]} · {INCIDENT_MANAGER_BRANCH_LABELS[incident.branch]}</p>
        </div>
        <p className="shrink-0 text-xs text-brand-anthracite/55">Updated {formatDate(incident.updated_at)}</p>
      </div>
      <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-brand-anthracite/80">{incident.description}</p>
      {nextStatuses.length > 0 && (
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Move to</span>
          {nextStatuses.map((status) => <Button key={status} variant="secondary" disabled={busy} loading={busy} onClick={() => void changeStatus(status)}>{INCIDENT_MANAGER_STATUS_LABELS[status]}</Button>)}
        </div>
      )}
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
    </article>
  );
}

function Summary({ summary }: { summary: IncidentSummary | null }) {
  if (!summary) return null;
  return (
    <section>
      <div className="flex items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Operational view</p><h2 className="mt-1 text-xl font-black">Incident summary</h2></div></div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <SummaryCard label="Total" value={summary.total} />
        <SummaryCard label="Open" value={summary.by_status.open ?? 0} tone="text-red-700" />
        <SummaryCard label="In progress" value={summary.by_status.in_progress ?? 0} tone="text-orange-700" />
        <SummaryCard label="Resolved" value={summary.by_status.resolved ?? 0} tone="text-green-700" />
        <SummaryCard label="Discarded" value={summary.by_status.discarded ?? 0} tone="text-zinc-500" />
      </div>
    </section>
  );
}

export function IncidentManagerPanel() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<IncidentSummary | null>(null);
  const [status, setStatus] = useState<IncidentManagerStatus | "">("");
  const [origin, setOrigin] = useState<IncidentManagerOrigin | "">("");
  const [branch, setBranch] = useState<IncidentManagerBranch | "">("");
  const [category, setCategory] = useState<IncidentManagerCategory | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const filters = useMemo(() => ({ status: status || undefined, origin: origin || undefined, branch: branch || undefined, category: category || undefined }), [branch, category, origin, status]);
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSummaryError(null);
    const [listResult, summaryResult] = await Promise.allSettled([listIncidents(filters), getIncidentSummary()]);
    if (listResult.status === "fulfilled") setIncidents(listResult.value);
    else setError(apiErrorMessage(listResult.reason));
    if (summaryResult.status === "fulfilled") setSummary(summaryResult.value);
    else setSummaryError(apiErrorMessage(summaryResult.reason));
    setLoading(false);
  }, [filters]);

  // The effect synchronizes this client component with the external API when filters change.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadData(); }, [loadData]);

  function addIncident(incident: Incident) {
    setIncidents((current) => [incident, ...current]);
    setSummary((current) => current ? { ...current, total: current.total + 1, by_status: { ...current.by_status, [incident.status]: current.by_status[incident.status] + 1 } } : current);
  }

  function updateIncident(incident: Incident) {
    setIncidents((current) => current.map((item) => item.id === incident.id ? incident : item));
    void loadData();
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Nexova operations</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Incident Manager</h1><p className="mt-3 text-sm leading-6 text-brand-anthracite/70">Capture operational incidents, keep ownership visible and move records through a controlled lifecycle.</p></div>
      <div className="mt-8"><IncidentForm onCreated={addIncident} /></div>
      <div className="mt-10"><Summary summary={summary} />{summaryError && <p role="alert" className="mt-3 text-sm text-red-700">{summaryError}</p>}</div>
      <section className="mt-10"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Current records</p><h2 className="mt-1 text-xl font-black">{incidents.length} incident{incidents.length === 1 ? "" : "s"}</h2></div>{loading && <Spinner size="sm" />}</div>
        <div className="mt-5 grid gap-4 rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:grid-cols-2 lg:grid-cols-4"><Select label="Filter by status" placeholder="All statuses" options={statusOptions} value={status} onChange={(event) => setStatus(event.target.value as IncidentManagerStatus | "")} /><Select label="Filter by origin" placeholder="All origins" options={originOptions} value={origin} onChange={(event) => setOrigin(event.target.value as IncidentManagerOrigin | "")} /><Select label="Filter by branch" placeholder="All branches" options={branchOptions} value={branch} onChange={(event) => setBranch(event.target.value as IncidentManagerBranch | "")} /><Select label="Filter by category" placeholder="All categories" options={categoryOptions} value={category} onChange={(event) => setCategory(event.target.value as IncidentManagerCategory | "")} /></div>
        {error && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
        {!loading && !error && incidents.length === 0 && <p className="mt-5 rounded-2xl border border-dashed border-brand-lightgray p-8 text-center text-sm text-brand-anthracite/60">No incidents match the selected filters.</p>}
        {!error && <div className="mt-5 space-y-4">{incidents.map((incident) => <IncidentRow key={incident.id} incident={incident} onUpdated={updateIncident} />)}</div>}
      </section>
    </div>
  );
}
