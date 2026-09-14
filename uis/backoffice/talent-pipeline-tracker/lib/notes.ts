import { apiFetch } from "./api";
import type { NoteOut, NotesListResponse, NoteCreate } from "@/types";

/** GET /records/{id}/notes — Obtener notas de un candidato */
export async function getNotes(recordId: string): Promise<NotesListResponse> {
  return apiFetch<NotesListResponse>(`/records/${recordId}/notes`);
}

/** POST /records/{id}/notes — Añadir una nota a un candidato */
export async function addNote(
  recordId: string,
  data: NoteCreate
): Promise<NoteOut> {
  return apiFetch<NoteOut>(`/records/${recordId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** DELETE /records/{id}/notes/{noteId} — Eliminar una nota */
export async function deleteNote(
  recordId: string,
  noteId: string
): Promise<void> {
  return apiFetch<void>(`/records/${recordId}/notes/${noteId}`, {
    method: "DELETE",
  });
}
