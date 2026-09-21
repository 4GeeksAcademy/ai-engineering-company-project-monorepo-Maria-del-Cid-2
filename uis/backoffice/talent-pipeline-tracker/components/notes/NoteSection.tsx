"use client";

import { useEffect } from "react";
import { useNotes } from "@/hooks";
import { NoteList } from "./NoteList";
import { NoteForm } from "./NoteForm";

interface NoteSectionProps {
  recordId: string;
}

export function NoteSection({ recordId }: NoteSectionProps) {
  const { notes, loading, error, fetchNotes, createNote, removeNote } =
    useNotes();

  useEffect(() => {
    fetchNotes(recordId);
  }, [recordId, fetchNotes]);

  const handleAddNote = async (content: string) => {
    await createNote(recordId, content);
  };

  const handleDeleteNote = async (noteId: string) => {
    await removeNote(recordId, noteId);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-sm font-semibold text-zinc-900">
        Notas internas
      </h2>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <NoteList
        notes={notes}
        loading={loading}
        onDelete={handleDeleteNote}
      />

      <NoteForm onSubmit={handleAddNote} />
    </div>
  );
}