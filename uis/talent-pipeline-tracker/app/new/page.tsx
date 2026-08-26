import { CandidateForm } from "@/components/candidates";

export default function NewCandidatePage() {
  return (
    <div className="mx-auto max-w-lg px-4 py-6 sm:px-6 lg:px-8">
      <h1 className="mb-6 text-xl font-bold text-zinc-900">
        Nueva candidatura
      </h1>
      <div className="rounded-lg border border-zinc-200 bg-white p-6">
        <CandidateForm />
      </div>
    </div>
  );
}
