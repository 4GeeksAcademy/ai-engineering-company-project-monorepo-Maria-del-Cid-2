import type { ApiStatus, ApiStage } from "@/types";

/** Mapeo de valores API → etiquetas legibles en la UI */
export const STATUS_LABELS: Record<ApiStatus, string> = {
  received: "Recibida",
  in_progress: "En proceso",
  selected: "Seleccionada",
  discarded: "Descartada",
};

export const STAGE_LABELS: Record<ApiStage, string> = {
  pending: "Pendiente de revisión",
  review: "En revisión",
  personal_interview: "Entrevista personal",
  technical_interview: "Entrevista técnica",
  offer_presented: "Oferta presentada",
};

/** Colores Tailwind para los badges de status */
export const STATUS_BADGE_COLORS: Record<ApiStatus, string> = {
  received: "bg-status-received text-nexova-800",
  in_progress: "bg-status-in-progress text-yellow-800",
  selected: "bg-status-selected text-green-800",
  discarded: "bg-status-discarded text-red-800",
};

/** Colores Tailwind para los badges de stage */
export const STAGE_BADGE_COLORS: Record<ApiStage, string> = {
  pending: "bg-stage-pending text-zinc-600",
  review: "bg-stage-review text-amber-800",
  personal_interview: "bg-stage-interview text-blue-800",
  technical_interview: "bg-stage-interview text-indigo-800",
  offer_presented: "bg-stage-offer text-emerald-800",
};

/** Lista de valores de status para selects/filtros */
export const STATUS_OPTIONS: { value: ApiStatus; label: string }[] = [
  { value: "received", label: "Recibida" },
  { value: "in_progress", label: "En proceso" },
  { value: "selected", label: "Seleccionada" },
  { value: "discarded", label: "Descartada" },
];

/** Lista de valores de stage para selects/filtros */
export const STAGE_OPTIONS: { value: ApiStage; label: string }[] = [
  { value: "pending", label: "Pendiente de revisión" },
  { value: "review", label: "En revisión" },
  { value: "personal_interview", label: "Entrevista personal" },
  { value: "technical_interview", label: "Entrevista técnica" },
  { value: "offer_presented", label: "Oferta presentada" },
];

/** Número de elementos por página por defecto */
export const DEFAULT_PAGE_LIMIT = 20;
