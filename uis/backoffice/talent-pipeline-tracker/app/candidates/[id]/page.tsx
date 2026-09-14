import { CandidateDetail } from "@/components/candidates";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CandidatePage({ params }: Props) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8">
      <CandidateDetail recordId={id} />
    </div>
  );
}
