"use client";

import { useState, useEffect, useCallback } from "react";
import { getRecordById, patchRecord, deleteRecord } from "@/lib/records";
import type { RecordOut, RecordPatch } from "@/types";

interface UseRecordReturn {
  record: RecordOut | null;
  loading: boolean;
  error: string | null;
  updateRecord: (data: RecordPatch) => Promise<void>;
  removeRecord: () => Promise<void>;
  refetch: () => void;
}

export function useRecord(id: string): UseRecordReturn {
  const [record, setRecord] = useState<RecordOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRecord = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getRecordById(id);
      setRecord(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al cargar el candidato"
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchRecord();
  }, [fetchRecord]);

  const updateRecord = useCallback(
    async (data: RecordPatch) => {
      setError(null);
      try {
        const updated = await patchRecord(id, data);
        setRecord(updated);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Error al actualizar"
        );
        throw err;
      }
    },
    [id]
  );

  const removeRecord = useCallback(async () => {
    setError(null);
    try {
      await deleteRecord(id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al eliminar"
      );
      throw err;
    }
  }, [id]);

  return {
    record,
    loading,
    error,
    updateRecord,
    removeRecord,
    refetch: fetchRecord,
  };
}
