import {
  IncidentAnalysisApiError,
  type IncidentAnalysisResult,
} from "@/types/incident-analysis";

const INCIDENT_ANALYSIS_API_BASE =
  process.env.NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE ?? "http://localhost:8000/api";

async function readErrorMessage(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return response.statusText || "Unknown API error";

  try {
    const parsed: unknown = JSON.parse(body);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "detail" in parsed &&
      typeof parsed.detail === "string"
    ) {
      return parsed.detail;
    }
  } catch {
    // Fall back to the raw response body when it is not JSON.
  }

  return body;
}

async function requestIncidentAnalysis<T>(
  endpoint: string,
  init?: RequestInit
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${INCIDENT_ANALYSIS_API_BASE}${endpoint}`, init);
  } catch {
    throw new IncidentAnalysisApiError(0, "Unable to reach Incident Analysis API");
  }

  if (!response.ok) {
    throw new IncidentAnalysisApiError(
      response.status,
      `Incident Analysis API error ${response.status} (${response.statusText}): ${await readErrorMessage(response)}`
    );
  }

  return response.json() as Promise<T>;
}

export async function analyzeIncidents(
  csvFile: File | Blob
): Promise<IncidentAnalysisResult> {
  const formData = new FormData();
  const filename =
    typeof File !== "undefined" && csvFile instanceof File
      ? csvFile.name
      : "incidents.csv";
  formData.append("file", csvFile, filename);

  // Do not set Content-Type: fetch must add the multipart boundary.
  return requestIncidentAnalysis<IncidentAnalysisResult>(
    "/incidents/analyze",
    {
      method: "POST",
      body: formData,
    }
  );
}

export async function exportIncidentResults(): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${INCIDENT_ANALYSIS_API_BASE}/incidents/results/export`);
  } catch {
    throw new IncidentAnalysisApiError(0, "Unable to reach Incident Analysis API");
  }

  if (!response.ok) {
    throw new IncidentAnalysisApiError(
      response.status,
      `Incident Analysis API error ${response.status} (${response.statusText}): ${await readErrorMessage(response)}`
    );
  }

  return response.blob();
}

export const analyzeIncidentCsv = analyzeIncidents;
export const downloadLatestIncidentResults = exportIncidentResults;
