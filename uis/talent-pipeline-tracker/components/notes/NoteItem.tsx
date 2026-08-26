"use client";

import { useState } from "react";
import { Button, Textarea, Spinner } from "@/components/ui";
import type { NoteOut } from "@/types";

interface NoteItemProps {
  note: NoteOut;
  onDelete: (noteId: string) => Promise<void>;
}

export function NoteItem({ note, onDelete }: NoteItemProps) {
  const [deleting, setDeleting] = useState(false);
  const formattedDate = new Date(note.created_at).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await onDelete(note.id);
    } catch {
      setDeleting(false);
    }
  };

  return (
    <div className="group flex items-start justify-between gap-3 rounded-lg border border-zinc-100 bg-zinc-50 p-3">
      <div className="min-w-0 flex-1">
        <p className="whitespace-pre-wrap text-sm text-zinc-700">
          {note.content}
        </p>
        <p className="mt-1 text-xs text-zinc-400">{formattedDate}</p>
      </div>
      <button
        onClick={handleDelete}
        disabled={deleting}
        className="shrink-0 rounded p-1 text-zinc-400 opacity-0 transition-all hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 disabled:opacity-50"
        aria-label="Eliminar nota"
      >
        {deleting ? (
          <Spinner size="sm" />
        ) : (
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        )}
      </button>
    </div>
  );
}