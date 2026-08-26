/** Valores que devuelve la API para status */
export type ApiStatus =
  | "received"
  | "in_progress"
  | "selected"
  | "discarded";

/** Valores que devuelve la API para stage */
export type ApiStage =
  | "pending"
  | "review"
  | "personal_interview"
  | "technical_interview"
  | "offer_presented";

/** Schema para crear un candidato (POST /records) */
export interface RecordCreate {
  full_name: string;
  email: string;
  phone: string;
  position: string;
  experience_years: number;
  linkedin_url?: string | null;
  cv_url?: string | null;
}

/** Schema para actualizar status/stage (PATCH /records/{id}) */
export interface RecordPatch {
  status?: ApiStatus | null;
  stage?: ApiStage | null;
}

/** Schema completo de un candidato devuelto por la API */
export interface RecordOut {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  position: string;
  linkedin_url: string | null;
  cv_url: string | null;
  status: ApiStatus;
  stage: ApiStage;
  experience_years: number;
  notes_count: number;
  applied_at: string;
  updated_at: string;
  notes?: Note[];
}

/** Nota incluida en el detalle del candidato */
export interface Note {
  id: string;
  record_id: string;
  content: string;
  created_at: string;
}
