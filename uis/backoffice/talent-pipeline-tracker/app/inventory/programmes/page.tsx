"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Button, Input, Spinner } from "@/components/ui";
import { createProgramme, inventoryErrorMessage, listProgrammes } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import type { Programme } from "@/types/inventory";

export default function ProgrammesPage() {
  const [programmes, setProgrammes] = useState<Programme[]>([]);
  const [programmeId, setProgrammeId] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listProgrammes(nexovaApi).then((items) => {
      if (active) setProgrammes(items);
    }).catch((failure) => {
      if (active) setError(inventoryErrorMessage(failure, "No se pudieron cargar los programas."));
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const created = await createProgramme(nexovaApi, { programme_id: programmeId.trim(), name: name.trim() });
      setProgrammes((current) => [...current, created].sort((first, second) => first.name.localeCompare(second.name)));
      setProgrammeId("");
      setName("");
    } catch (failure) {
      setError(inventoryErrorMessage(failure, "No se pudo crear el programa."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-black">Programmes</h1>
      <form onSubmit={submit} className="mt-8 grid gap-4 border-b border-brand-lightgray pb-8 sm:grid-cols-[1fr_2fr_auto] sm:items-end">
        <Input label="Programme ID" required value={programmeId} onChange={(event) => setProgrammeId(event.target.value)} />
        <Input label="Name" required value={name} onChange={(event) => setName(event.target.value)} />
        <Button type="submit" loading={saving}>Create programme</Button>
      </form>
      {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
      {loading ? <div className="mt-8"><Spinner size="sm" /></div> : (
        <section className="mt-8" aria-label="Programmes list">
          {programmes.length === 0 ? <p>No programmes available.</p> : (
            <ul className="divide-y divide-brand-lightgray">
              {programmes.map((programme) => (
                <li key={programme.programme_id} className="flex flex-wrap justify-between gap-2 py-4">
                  <span className="font-semibold">{programme.name}</span>
                  <span className="font-mono text-sm text-brand-anthracite/65">{programme.programme_id}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  );
}