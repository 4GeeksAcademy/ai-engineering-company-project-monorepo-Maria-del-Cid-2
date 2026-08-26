"use client";

import { NoteItem } from "./NoteItem";
import { Spinner } from "@/components/ui";
import type { NoteOut } from "@/types";

interface NoteListProps {
  notes: NoteOut[];
  loading: boolean;
  onDelete: (noteId: string) => Promise<void>;
}

export function NoteList({ notes, loading, onDelete }: NoteListProps) {
  if (loading) {
    return (
      <div className="flex justify-center py-6">
        <Spinner size="sm" />
      </div>
    );
  }

  if (notes.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-zinc-400">
        No hay notas internas todavía.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {notes.map((note) => (
        <NoteItem key={note.id} note={note} onDelete={onDelete} />
      ))}
    </div>
  );
}