"use client";

import { Select } from "@/components/ui";
import { STATUS_OPTIONS, STAGE_OPTIONS } from "@/constants";
import type { ApiStatus, ApiStage } from "@/types";

interface FilterBarProps {
  status: string | undefined;
  stage: string | undefined;
  onStatusChange: (status: string) => void;
  onStageChange: (stage: string) => void;
  onClear: () => void;
}

export function FilterBar({
  status,
  stage,
  onStatusChange,
  onStageChange,
  onClear,
}: FilterBarProps) {
  const hasFilters = status || stage;

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-44">
        <Select
          label="Estado"
          placeholder="Todos los estados"
          value={status ?? ""}
          onChange={(e) => onStatusChange(e.target.value)}
          options={STATUS_OPTIONS}
        />
      </div>
      <div className="w-48">
        <Select
          label="Etapa"
          placeholder="Todas las etapas"
          value={stage ?? ""}
          onChange={(e) => onStageChange(e.target.value)}
          options={STAGE_OPTIONS}
        />
      </div>
      {hasFilters && (
        <button
          onClick={onClear}
          className="mb-0.5 rounded-lg px-3 py-2 text-sm text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
        >
          Limpiar filtros
        </button>
      )}
    </div>
  );
}