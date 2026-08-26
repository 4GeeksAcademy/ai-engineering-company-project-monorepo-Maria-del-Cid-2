import Link from "next/link";
import { StatusBadge, StageBadge } from "./StatusBadge";
import type { RecordOut } from "@/types";

interface CandidateCardProps {
  record: RecordOut;
}

export function CandidateCard({ record }: CandidateCardProps) {
  const formattedDate = new Date(record.applied_at).toLocaleDateString("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  return (
    <Link
      href={`/candidates/${record.id}`}
      className="block rounded-lg border border-zinc-200 bg-white p-4 transition-colors hover:border-nexova-300 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-zinc-900">
            {record.full_name}
          </h3>
          <p className="mt-0.5 truncate text-sm text-zinc-500">
            {record.position}
          </p>
          <p className="mt-0.5 truncate text-xs text-zinc-400">
            {record.email}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <StatusBadge status={record.status} />
          <StageBadge stage={record.stage} />
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3 text-xs text-zinc-400">
        <span>
          {record.experience_years} año{record.experience_years !== 1 ? "s" : ""} de exp.
        </span>
        <span>·</span>
        <span>{formattedDate}</span>
        {record.notes_count > 0 && (
          <>
            <span>·</span>
            <span>{record.notes_count} nota{record.notes_count !== 1 ? "s" : ""}</span>
          </>
        )}
      </div>
    </Link>
  );
}