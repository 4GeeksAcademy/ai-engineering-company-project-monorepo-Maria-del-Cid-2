"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useRecord } from "@/hooks";
import { StatusBadge, StageBadge } from "./StatusBadge";
import { Button, Spinner } from "@/components/ui";
import { NoteSection } from "@/components/notes";
import { STATUS_OPTIONS, STAGE_OPTIONS } from "@/constants";
import type { ApiStatus, ApiStage } from "@/types";

interface CandidateDetailProps {
  recordId: string;
}

export function CandidateDetail({ recordId }: CandidateDetailProps) {
  const router = useRouter();
  const { record, loading, error, updateRecord, removeRecord } =
    useRecord(recordId);

  const [newStatus, setNewStatus] = useState<ApiStatus | "">("");
  const [newStage, setNewStage] = useState<ApiStage | "">("");
  const [updating, setUpdating] = useState(false);
  const [deleting, setDeleting] = useState(false);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-8 text-center">
        <p className="text-sm text-red-700">
          {error || "Candidato no encontrado"}
        </p>
        <Button variant="ghost" onClick={() => router.back()} className="mt-4">
          Volver
        </Button>
      </div>
    );
  }

  const formattedDate = new Date(record.applied_at).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const handleUpdate = async () => {
    const patch: { status?: ApiStatus; stage?: ApiStage } = {};
    if (newStatus) patch.status = newStatus as ApiStatus;
    if (newStage) patch.stage = newStage as ApiStage;

    if (Object.keys(patch).length === 0) return;

    setUpdating(true);
    try {
      await updateRecord(patch);
      setNewStatus("");
      setNewStage("");
    } catch {
      // error is handled by the hook
    } finally {
      setUpdating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("¿Estás seguro de eliminar esta candidatura?")) return;
    setDeleting(true);
    try {
      await removeRecord();
      router.push("/");
    } catch {
      // error is handled by the hook
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => router.push("/")}
          className="mb-4 text-sm text-nexova-600 hover:text-nexova-700"
        >
          ← Volver al listado
        </button>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-zinc-900">
              {record.full_name}
            </h1>
            <p className="mt-1 text-sm text-zinc-500">{record.position}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={record.status} />
            <StageBadge stage={record.stage} />
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="grid gap-4 rounded-lg border border-zinc-200 bg-white p-4 sm:grid-cols-2">
        <div>
          <span className="text-xs font-medium text-zinc-400">Email</span>
          <p className="text-sm text-zinc-900">{record.email}</p>
        </div>
        <div>
          <span className="text-xs font-medium text-zinc-400">Teléfono</span>
          <p className="text-sm text-zinc-900">{record.phone}</p>
        </div>
        <div>
          <span className="text-xs font-medium text-zinc-400">
            Años de experiencia
          </span>
          <p className="text-sm text-zinc-900">{record.experience_years}</p>
        </div>
        <div>
          <span className="text-xs font-medium text-zinc-400">
            Fecha de aplicación
          </span>
          <p className="text-sm text-zinc-900">{formattedDate}</p>
        </div>
        {record.linkedin_url && (
          <div className="sm:col-span-2">
            <span className="text-xs font-medium text-zinc-400">LinkedIn</span>
            <a
              href={record.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate text-sm text-nexova-600 hover:underline"
            >
              {record.linkedin_url}
            </a>
          </div>
        )}
        {record.cv_url && (
          <div className="sm:col-span-2">
            <span className="text-xs font-medium text-zinc-400">CV</span>
            <a
              href={record.cv_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate text-sm text-nexova-600 hover:underline"
            >
              {record.cv_url}
            </a>
          </div>
        )}
      </div>

      {/* Update Status / Stage */}
      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-zinc-900">
          Actualizar estado y etapa
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              Estado
            </label>
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value as ApiStatus | "")}
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-nexova-500 focus:outline-none focus:ring-2 focus:ring-nexova-200"
            >
              <option value="">Mantener actual</option>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1">
            <label className="mb-1 block text-xs font-medium text-zinc-500">
              Etapa
            </label>
            <select
              value={newStage}
              onChange={(e) => setNewStage(e.target.value as ApiStage | "")}
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm focus:border-nexova-500 focus:outline-none focus:ring-2 focus:ring-nexova-200"
            >
              <option value="">Mantener actual</option>
              {STAGE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <Button
            onClick={handleUpdate}
            loading={updating}
            disabled={!newStatus && !newStage}
          >
            Actualizar
          </Button>
        </div>
      </div>

      {/* Notes */}
      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <NoteSection recordId={record.id} />
      </div>

      {/* Delete */}
      <div className="flex justify-end border-t border-zinc-200 pt-4">
        <Button
          variant="danger"
          onClick={handleDelete}
          loading={deleting}
        >
          Eliminar candidatura
        </Button>
      </div>
    </div>
  );
}