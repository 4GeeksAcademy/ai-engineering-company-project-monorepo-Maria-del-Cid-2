"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { getRecords } from "@/lib/records";
import type { RecordOut, RecordsQueryParams, PaginatedResponse } from "@/types";
import { DEFAULT_PAGE_LIMIT } from "@/constants";

interface UseRecordsReturn {
  records: RecordOut[];
  total: number;
  page: number;
  totalPages: number;
  loading: boolean;
  error: string | null;
  /** Valor actual del filtro status (leído de la URL) */
  statusFilter: string;
  /** Valor actual del filtro stage (leído de la URL) */
  stageFilter: string;
  /** Valor actual del filtro search (leído de la URL) */
  searchFilter: string;
  /** Actualiza status en la URL y resetea a página 1 */
  setStatusFilter: (status: string) => void;
  /** Actualiza stage en la URL y resetea a página 1 */
  setStageFilter: (stage: string) => void;
  /** Actualiza search en la URL y resetea a página 1 */
  setSearchFilter: (search: string) => void;
  /** Limpia status, stage y search de la URL, resetea a página 1 */
  clearFilters: () => void;
  /** Cambia de página (se refleja en la URL) */
  setPage: (page: number) => void;
  /** Refuerza la recarga de datos */
  refetch: () => void;
}

export function useRecords(): UseRecordsReturn {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // Todos los filtros se leen directamente de la URL
  const statusFromUrl = searchParams.get("status") ?? "";
  const stageFromUrl = searchParams.get("stage") ?? "";
  const searchFromUrl = searchParams.get("search") ?? "";
  const pageFromUrl = Math.max(1, Number(searchParams.get("page")) || 1);

  const [data, setData] = useState<PaginatedResponse<RecordOut> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Construir los params que se mandan a la API
  const apiParams: RecordsQueryParams = {
    status: statusFromUrl || undefined,
    stage: stageFromUrl || undefined,
    search: searchFromUrl || undefined,
    page: pageFromUrl,
    limit: DEFAULT_PAGE_LIMIT,
  };

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRecords(apiParams);
      setData(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al cargar candidaturas"
      );
    } finally {
      setLoading(false);
    }
  }, [statusFromUrl, stageFromUrl, searchFromUrl, pageFromUrl]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  /** Construye y navega a una nueva URL con los query params dados.
   *  Toma los valores actuales de la URL como base y aplica overrides. */
  const navigateWithParams = useCallback(
    (overrides: {
      status?: string;
      stage?: string;
      search?: string;
      page?: number;
      clearAll?: boolean;
    }) => {
      const params = new URLSearchParams();

      if (overrides.clearAll) {
        // No añadimos nada, URL limpia
      } else {
        const s = overrides.status !== undefined ? overrides.status : statusFromUrl;
        const st = overrides.stage !== undefined ? overrides.stage : stageFromUrl;
        const srch = overrides.search !== undefined ? overrides.search : searchFromUrl;
        const p = overrides.page ?? 1;

        if (s) params.set("status", s);
        if (st) params.set("stage", st);
        if (srch) params.set("search", srch);
        if (p > 1) params.set("page", String(p));
      }

      const qs = params.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [statusFromUrl, stageFromUrl, searchFromUrl, pathname, router]
  );

  const setStatusFilter = useCallback(
    (status: string) => {
      navigateWithParams({ status, page: 1 });
    },
    [navigateWithParams]
  );

  const setStageFilter = useCallback(
    (stage: string) => {
      navigateWithParams({ stage, page: 1 });
    },
    [navigateWithParams]
  );

  const setSearchFilter = useCallback(
    (search: string) => {
      navigateWithParams({ search, page: 1 });
    },
    [navigateWithParams]
  );

  const clearFilters = useCallback(() => {
    navigateWithParams({ clearAll: true });
  }, [navigateWithParams]);

  const setPage = useCallback(
    (page: number) => {
      navigateWithParams({ page });
    },
    [navigateWithParams]
  );

  return {
    records: data?.data ?? [],
    total: data?.total ?? 0,
    page: pageFromUrl,
    totalPages: data ? Math.ceil(data.total / data.limit) : 0,
    loading,
    error,
    statusFilter: statusFromUrl,
    stageFilter: stageFromUrl,
    searchFilter: searchFromUrl,
    setStatusFilter,
    setStageFilter,
    setSearchFilter,
    clearFilters,
    setPage,
    refetch: fetchRecords,
  };
}
