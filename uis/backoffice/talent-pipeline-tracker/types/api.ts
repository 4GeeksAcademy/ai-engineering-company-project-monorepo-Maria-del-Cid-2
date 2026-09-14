/** Respuesta paginada del endpoint GET /records */
export interface PaginatedResponse<T> {
  total: number;
  page: number;
  limit: number;
  data: T[];
}

/** Parámetros de consulta para GET /records */
export interface RecordsQueryParams {
  status?: string;
  stage?: string;
  search?: string;
  page?: number;
  limit?: number;
}
