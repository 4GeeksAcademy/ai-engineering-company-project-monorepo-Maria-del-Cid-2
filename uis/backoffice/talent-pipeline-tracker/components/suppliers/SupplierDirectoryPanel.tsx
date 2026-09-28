"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Input, Modal, Select, Spinner } from "@/components/ui";
import {
  createSupplier,
  deleteSupplier,
  listSuppliers,
  updateSupplierRate,
  updateSupplierStatus,
} from "@/lib/suppliers-api";
import {
  SUPPLIER_CATEGORIES,
  SUPPLIER_CATEGORY_LABELS,
  SUPPLIER_COUNTRIES,
  type Supplier,
  type SupplierCategory,
  type SupplierCountry,
  type SupplierCreatePayload,
  type SupplierStatus,
} from "@/types/supplier";

const categoryOptions = SUPPLIER_CATEGORIES.map((value) => ({
  value,
  label: SUPPLIER_CATEGORY_LABELS[value],
}));
const countryOptions = SUPPLIER_COUNTRIES.map((value) => ({ value, label: value }));
const statusOptions = [
  { value: "active", label: "Active" },
  { value: "suspended", label: "Suspended" },
];

function isRenewalSoon(date: string | null): boolean {
  if (!date) return false;
  const renewal = new Date(`${date}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = (renewal.getTime() - today.getTime()) / 86_400_000;
  return days >= 0 && days <= 60;
}

function apiErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to complete the request.";
}

function SupplierForm({ onCreated }: { onCreated: (supplier: Supplier) => void }) {
  const [form, setForm] = useState<SupplierCreatePayload>({
    name: "",
    country: "Spain",
    categories: ["job_boards"],
    monthly_rate: 0,
    currency: "EUR",
    status: "active",
    contract_renewal_date: "",
    contact_email: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof SupplierCreatePayload>(key: K, value: SupplierCreatePayload[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload = {
      ...form,
      monthly_rate: Number(form.monthly_rate),
      contract_renewal_date: form.contract_renewal_date || undefined,
      contact_email: form.contact_email || undefined,
      notes: form.notes || undefined,
    };
    try {
      const created = await createSupplier(payload);
      onCreated(created);
      setForm((current) => ({ ...current, name: "", monthly_rate: 0, contact_email: "", notes: "", contract_renewal_date: "" }));
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:p-6">
      <div>
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Directory maintenance</p>
        <h2 className="mt-1 text-xl font-black tracking-tight">Add supplier</h2>
      </div>
      <form className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" onSubmit={submit}>
        <Input label="Name" required value={form.name} onChange={(event) => updateField("name", event.target.value)} />
        <Select label="Country" options={countryOptions} value={form.country} onChange={(event) => {
          const nextCountry = event.target.value as SupplierCountry;
          setForm((current) => ({ ...current, country: nextCountry, currency: nextCountry === "Spain" ? "EUR" : "USD" }));
        }} />
        <Select label="Category" options={categoryOptions} value={form.categories[0]} onChange={(event) => updateField("categories", [event.target.value as SupplierCategory])} />
        <Input label="Monthly rate" required min={0.01} step="0.01" type="number" value={form.monthly_rate || ""} onChange={(event) => updateField("monthly_rate", Number(event.target.value))} />
        <Select label="Currency" options={[{ value: "EUR", label: "EUR" }, { value: "USD", label: "USD" }]} value={form.currency} onChange={(event) => updateField("currency", event.target.value as "EUR" | "USD")} />
        <Select label="Status" options={statusOptions} value={form.status} onChange={(event) => updateField("status", event.target.value as SupplierStatus)} />
        <Input label="Renewal date" type="date" value={form.contract_renewal_date} onChange={(event) => updateField("contract_renewal_date", event.target.value)} />
        <Input label="Contact email" type="email" value={form.contact_email} onChange={(event) => updateField("contact_email", event.target.value)} />
        <Input label="Notes" value={form.notes} onChange={(event) => updateField("notes", event.target.value)} />
        {error && <p role="alert" className="sm:col-span-2 lg:col-span-3 text-sm text-red-700">{error}</p>}
        <div className="sm:col-span-2 lg:col-span-3"><Button type="submit" loading={saving}>Create supplier</Button></div>
      </form>
    </section>
  );
}

function SupplierRow({ supplier, onChange, onDelete }: { supplier: Supplier; onChange: (supplier: Supplier) => void; onDelete: (id: number) => void }) {
  const [rate, setRate] = useState(String(supplier.monthly_rate));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notesOpen, setNotesOpen] = useState(false);
  const renewalSoon = isRenewalSoon(supplier.contract_renewal_date);

  async function changeRate() {
    setBusy(true); setError(null);
    try { onChange(await updateSupplierRate(supplier.id, Number(rate))); }
    catch (requestError) { setError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }

  async function changeStatus() {
    setBusy(true); setError(null);
    try { onChange(await updateSupplierStatus(supplier.id, supplier.status === "active" ? "suspended" : "active")); }
    catch (requestError) { setError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm(`Delete ${supplier.name}?`)) return;
    setBusy(true); setError(null);
    try { await deleteSupplier(supplier.id); onDelete(supplier.id); }
    catch (requestError) { setError(apiErrorMessage(requestError)); }
    finally { setBusy(false); }
  }

  return (
    <article className={`rounded-2xl border p-5 shadow-sm ${supplier.status === "suspended" ? "border-zinc-300 bg-zinc-50" : "border-brand-lightgray bg-brand-white"}`}>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-black">{supplier.name}</h3>
            <Badge className={supplier.status === "active" ? "bg-green-100 text-green-800" : "bg-zinc-200 text-zinc-700"}>{supplier.status === "active" ? "Active" : "Suspended"}</Badge>
            {renewalSoon && <Badge className="bg-orange-100 text-orange-800">Renewal within 60 days</Badge>}
          </div>
          <p className="mt-1 text-sm text-brand-anthracite/65">{supplier.country} · {supplier.categories.map((category) => SUPPLIER_CATEGORY_LABELS[category]).join(", ")}</p>
        </div>
        <Button variant="secondary" className="w-fit text-red-700 hover:bg-red-50 hover:text-red-800" disabled={busy} onClick={remove}>Delete</Button>
      </div>
      <div className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-5">
        <div><p className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Monthly rate</p><div className="mt-1 flex gap-2"><input aria-label={`Rate for ${supplier.name}`} className="w-28 rounded-lg border border-zinc-300 px-2 py-1" type="number" min="0.01" step="0.01" value={rate} onChange={(event) => setRate(event.target.value)} /><Button variant="secondary" loading={busy} onClick={changeRate}>Save</Button></div></div>
        <div><p className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Renewal</p><p className="mt-1 font-semibold">{supplier.contract_renewal_date ?? "Not specified"}</p></div>
        <div><p className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Currency</p><p className="mt-1 font-semibold">{supplier.currency}</p></div>
        <div><p className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Contact email</p>{supplier.contact_email ? <a className="mt-1 block truncate font-semibold text-brand-orange hover:underline" href={`mailto:${supplier.contact_email}`}>{supplier.contact_email}</a> : <p className="mt-1 font-semibold">—</p>}</div>
        <div><p className="text-xs font-bold uppercase tracking-wider text-brand-anthracite/50">Status</p><div className="mt-1 flex flex-col items-start gap-2"><span className="font-semibold">{supplier.status === "active" ? "Active" : "Suspended"}</span><Button variant="secondary" disabled={busy} onClick={changeStatus}>Change status</Button></div></div>
      </div>
      {supplier.notes && <div className="mt-4"><Button variant="secondary" onClick={() => setNotesOpen(true)}>View notes</Button></div>}
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      <Modal open={notesOpen} onClose={() => setNotesOpen(false)} title={`Notes — ${supplier.name}`}>
        <p className="whitespace-pre-wrap text-sm leading-6 text-brand-anthracite/80">{supplier.notes}</p>
      </Modal>
    </article>
  );
}

export function SupplierDirectoryPanel() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [country, setCountry] = useState<SupplierCountry | "">("");
  const [category, setCategory] = useState<SupplierCategory | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSuppliers = useCallback(async () => {
    setLoading(true); setError(null);
    try { setSuppliers(await listSuppliers({ country: country || undefined, category: category || undefined })); }
    catch (requestError) { setError(apiErrorMessage(requestError)); }
    finally { setLoading(false); }
  }, [country, category]);

  // The effect synchronizes the component with the external API when filters change.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadSuppliers(); }, [loadSuppliers]);
  const emptyLabel = useMemo(() => country || category ? "No suppliers match these filters." : "No suppliers have been added yet.", [country, category]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl"><p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Nexova operations</p><h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Supplier Directory</h1><p className="mt-3 text-sm leading-6 text-brand-anthracite/70">Manage the external platforms and services used by Nexova Valencia and Miami.</p></div>
      <div className="mt-8 grid gap-4 rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:grid-cols-2"><Select label="Filter by country" placeholder="All countries" options={countryOptions} value={country} onChange={(event) => setCountry(event.target.value as SupplierCountry | "")} /><Select label="Filter by category" placeholder="All categories" options={categoryOptions} value={category} onChange={(event) => setCategory(event.target.value as SupplierCategory | "")} /></div>
      <div className="mt-8"><SupplierForm onCreated={(supplier) => setSuppliers((current) => [supplier, ...current])} /></div>
      <section className="mt-10"><div className="flex items-center justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Current records</p><h2 className="mt-1 text-xl font-black">{suppliers.length} supplier{suppliers.length === 1 ? "" : "s"}</h2></div>{loading && <Spinner size="sm" />}</div>{error && <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}{!loading && !error && suppliers.length === 0 && <p className="mt-5 rounded-2xl border border-dashed border-brand-lightgray p-8 text-center text-sm text-brand-anthracite/60">{emptyLabel}</p>}{!loading && <div className="mt-5 space-y-4">{suppliers.map((supplier) => <SupplierRow key={supplier.id} supplier={supplier} onChange={(updated) => setSuppliers((current) => current.map((item) => item.id === updated.id ? updated : item))} onDelete={(id) => setSuppliers((current) => current.filter((item) => item.id !== id))} />)}</div>}</section>
    </div>
  );
}
