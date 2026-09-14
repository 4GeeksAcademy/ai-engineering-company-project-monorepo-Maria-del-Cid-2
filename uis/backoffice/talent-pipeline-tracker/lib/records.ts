import { apiFetch } from "./api";
import type {
  RecordCreate,
  RecordOut,
  RecordPatch,
  PaginatedResponse,
  RecordsQueryParams,
} from "@/types";

/** GET /records — Obtener listado paginado con filtros */
export async function getRecords(
  params: RecordsQueryParams = {}
): Promise<PaginatedResponse<RecordOut>> {
  return apiFetch<PaginatedResponse<RecordOut>>("/records", {
    params: {
      status: params.status,
      stage: params.stage,
      search: params.search,
      page: params.page,
      limit: params.limit,
    },
  });
}

/** GET /records/{id} — Obtener detalle de un candidato */
export async function getRecordById(id: string): Promise<RecordOut> {
  return apiFetch<RecordOut>(`/records/${id}`);
}

/** POST /records — Crear un nuevo candidato */
export async function createRecord(
  data: RecordCreate
): Promise<RecordOut> {
  return apiFetch<RecordOut>("/records", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** PATCH /records/{id} — Actualizar status/stage de un candidato */
export async function patchRecord(
  id: string,
  data: RecordPatch
): Promise<RecordOut> {
  return apiFetch<RecordOut>(`/records/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

/** PUT /records/{id} — Reemplazar todos los campos de un candidato */
export async function replaceRecord(
  id: string,
  data: RecordCreate
): Promise<RecordOut> {
  return apiFetch<RecordOut>(`/records/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/** DELETE /records/{id} — Eliminar un candidato */
export async function deleteRecord(id: string): Promise<void> {
  return apiFetch<void>(`/records/${id}`, {
    method: "DELETE",
  });
}
