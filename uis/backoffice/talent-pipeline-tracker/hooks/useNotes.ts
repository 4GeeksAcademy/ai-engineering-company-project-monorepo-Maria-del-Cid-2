"use client";

import { useState, useCallback } from "react";
import { getNotes, addNote, deleteNote } from "@/lib/notes";
import type { NoteOut } from "@/types";

interface UseNotesReturn {
  notes: NoteOut[];
  loading: boolean;
  error: string | null;
  fetchNotes: (recordId: string) => Promise<void>;
  createNote: (recordId: string, content: string) => Promise<void>;
  removeNote: (recordId: string, noteId: string) => Promise<void>;
}

export function useNotes(): UseNotesReturn {
  const [notes, setNotes] = useState<NoteOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchNotes = useCallback(async (recordId: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getNotes(recordId);
      setNotes(result.data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Error al cargar notas"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const createNote = useCallback(
    async (recordId: string, content: string) => {
      setError(null);
      try {
        const newNote = await addNote(recordId, { content });
        setNotes((prev) => [...prev, newNote]);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Error al añadir nota"
        );
        throw err;
      }
    },
    []
  );

  const removeNote = useCallback(
    async (recordId: string, noteId: string) => {
      setError(null);
      try {
        await deleteNote(recordId, noteId);
        setNotes((prev) => prev.filter((n) => n.id !== noteId));
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Error al eliminar nota"
        );
        throw err;
      }
    },
    []
  );

  return {
    notes,
    loading,
    error,
    fetchNotes,
    createNote,
    removeNote,
  };
}
