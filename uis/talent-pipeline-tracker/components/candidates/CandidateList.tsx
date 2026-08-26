"use client";

import { CandidateCard } from "./CandidateCard";
import { Spinner } from "@/components/ui";
import type { RecordOut } from "@/types";

interface CandidateListProps {
  records: RecordOut[];
  loading: boolean;
  error: string | null;
}

export function CandidateList({ records, loading, error }: CandidateListProps) {
  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center">
        <p className="text-sm text-red-700">{error}</p>
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-300 bg-white px-4 py-12 text-center">
        <p className="text-sm text-zinc-500">
          No se encontraron candidaturas con los filtros seleccionados.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {records.map((record) => (
        <CandidateCard key={record.id} record={record} />
      ))}
    </div>
  );
}