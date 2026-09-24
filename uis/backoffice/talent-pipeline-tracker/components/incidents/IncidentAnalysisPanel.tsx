"use client";

import { DragEvent, useRef, useState } from "react";
import { analyzeIncidents, exportIncidentResults } from "@/lib/incident-analysis-api";
import {
  INCIDENT_CATEGORIES,
  INCIDENT_STATUSES,
  VALIDATION_ERROR_CODES,
  type IncidentAnalysisResult,
} from "@/types/incident-analysis";
import { Button, Spinner } from "@/components/ui";

const errorLabels: Record<(typeof VALIDATION_ERROR_CODES)[number], string> = {
  missing_client_company: "Missing client/company",
  invalid_category: "Invalid category",
  invalid_description: "Invalid description",
  invalid_agent_id: "Invalid agent ID",
  invalid_email: "Invalid email",
  closed_without_satisfaction_score: "Closed without satisfaction score",
  satisfaction_score_out_of_range: "Satisfaction score out of range",
};

const categoryLabels: Record<(typeof INCIDENT_CATEGORIES)[number], string> = {
  TECHNICAL: "Technical",
  BILLING: "Billing",
  ACCESS: "Access",
  HR_QUERY: "HR query",
  COMPLAINT: "Complaint",
};

const statusLabels: Record<(typeof INCIDENT_STATUSES)[number], string> = {
  OPEN: "Open",
  CLOSED: "Closed",
  DISCARDED: "Discarded",
};

function countOf(values: Record<string, number> | undefined, key: string) {
  return values?.[key] ?? 0;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.12em] text-brand-anthracite/55">
        {label}
      </p>
      <p className="mt-2 text-3xl font-black tracking-tight text-brand-anthracite">
        {value}
      </p>
    </div>
  );
}

function Breakdown({
  title,
  values,
  labels,
}: {
  title: string;
  values: Record<string, number>;
  labels: Record<string, string>;
}) {
  return (
    <section className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <h2 className="text-sm font-bold uppercase tracking-[0.12em] text-brand-anthracite">
        {title}
      </h2>
      <div className="mt-4 space-y-3">
        {Object.entries(labels).map(([key, label]) => {
          const value = countOf(values, key);
          return (
            <div className="flex items-center justify-between gap-4" key={key}>
              <span className="text-sm text-brand-anthracite/75">{label}</span>
              <span className="min-w-8 rounded-full bg-nexova-50 px-2 py-1 text-center text-sm font-bold text-nexova-700">
                {value}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Results({ result }: { result: IncidentAnalysisResult }) {
  return (
    <div className="mt-10 space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
            Analysis complete
          </p>
          <h2 className="mt-1 text-xl font-black tracking-tight">Aggregated results</h2>
        </div>
        <DownloadButton />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Total records" value={result.total_records} />
        <MetricCard label="Valid records" value={result.valid_records} />
        <MetricCard label="Invalid records" value={result.invalid_records} />
        <MetricCard
          label="Average satisfaction"
          value={result.average_satisfaction === null ? "—" : result.average_satisfaction.toFixed(2)}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Breakdown title="By category" values={result.by_category} labels={categoryLabels} />
        <Breakdown title="By status" values={result.by_status} labels={statusLabels} />
        <Breakdown
          title="Satisfaction distribution"
          values={result.satisfaction_distribution}
          labels={{ 1: "1", 2: "2", 3: "3", 4: "4", 5: "5" }}
        />
        <Breakdown
          title="Validation errors"
          values={result.invalid_by_type}
          labels={errorLabels}
        />
      </div>
    </div>
  );
}

function DownloadButton() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    try {
      const blob = await exportIncidentResults();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "results.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (downloadError) {
      setError(downloadError instanceof Error ? downloadError.message : "Unable to download results.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex flex-col items-stretch gap-2 sm:items-end">
      <Button variant="secondary" loading={downloading} onClick={handleDownload}>
        Download results.csv
      </Button>
      {error && <p className="text-right text-xs text-red-700">{error}</p>}
    </div>
  );
}

export function IncidentAnalysisPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<IncidentAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [dragging, setDragging] = useState(false);

  function selectFile(nextFile: File | undefined) {
    setError(null);
    setResult(null);
    if (!nextFile) return;
    if (!nextFile.name.toLowerCase().endsWith(".csv")) {
      setFile(null);
      setError("Please select a CSV file.");
      return;
    }
    setFile(nextFile);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files[0]);
  }

  async function handleAnalyze() {
    if (!file || analyzing) return;
    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      setResult(await analyzeIncidents(file));
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Unable to analyze the file.");
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">Nexova operations</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Incident Analysis</h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Upload an incident CSV to review aggregate quality and satisfaction metrics. Original rows are never displayed.
        </p>
      </div>

      <div
        className={`mt-8 rounded-2xl border-2 border-dashed p-6 transition-colors sm:p-8 ${dragging ? "border-brand-orange bg-nexova-50" : "border-brand-lightgray bg-brand-white"}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (event.currentTarget === event.target) setDragging(false);
        }}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-nexova-100 text-xl text-nexova-700">↑</span>
          <h2 className="mt-4 text-lg font-bold">Choose a CSV file</h2>
          <p className="mt-1 text-sm text-brand-anthracite/60">or drag and drop it here</p>
          <input
            ref={inputRef}
            className="sr-only"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => selectFile(event.target.files?.[0])}
          />
          <Button variant="secondary" className="mt-5" onClick={() => inputRef.current?.click()}>
            Select file
          </Button>
          {file && <p className="mt-4 text-sm font-semibold text-brand-anthracite">Selected: {file.name}</p>}
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <Button disabled={!file} loading={analyzing} onClick={handleAnalyze}>
          {analyzing ? "Analyzing" : "Analyze incidents"}
        </Button>
        {analyzing && (
          <span className="flex items-center gap-2 text-sm text-brand-anthracite/60">
            <Spinner size="sm" /> Processing securely…
          </span>
        )}
      </div>

      {result && <Results result={result} />}
    </div>
  );
}
