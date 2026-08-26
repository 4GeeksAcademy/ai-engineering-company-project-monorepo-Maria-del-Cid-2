"use client";

import { useState } from "react";
import { Button, Textarea } from "@/components/ui";

interface NoteFormProps {
  onSubmit: (content: string) => Promise<void>;
}

export function NoteForm({ onSubmit }: NoteFormProps) {
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setSubmitting(true);
    try {
      await onSubmit(content.trim());
      setContent("");
    } catch {
      // error handled by parent
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-start gap-2">
      <Textarea
        placeholder="Añadir nota interna (después de llamada, entrevista, etc.)"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="flex-1"
      />
      <Button
        type="submit"
        loading={submitting}
        disabled={!content.trim()}
        className="mt-1"
      >
        Añadir
      </Button>
    </form>
  );
}