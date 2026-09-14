/** Schema para crear una nota (POST /records/{id}/notes) */
export interface NoteCreate {
  content: string;
}

/** Nota devuelta por la API */
export interface NoteOut {
  id: string;
  record_id: string;
  content: string;
  created_at: string;
}

/** Respuesta del endpoint GET /records/{id}/notes */
export interface NotesListResponse {
  data: NoteOut[];
  meta: {
    total: number;
  };
}
