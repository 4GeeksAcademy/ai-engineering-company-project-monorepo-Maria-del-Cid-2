import {
  IncidentAnalysisApiError,
  type IncidentAnalysisResult,
} from "../types/incident-analysis.ts";
import {
  createRequestSignal,
  DEFAULT_API_TIMEOUT_MS,
  isAbortError,
  parseHttpError,
  readResponseBody,
} from "./api-errors.ts";

const INCIDENT_ANALYSIS_API_BASE =
  process.env.NEXT_PUBLIC_INCIDENT_ANALYSIS_API_BASE ?? "http://localhost:8000/api";

export interface IncidentAnalysisRequestOptions extends RequestInit {
  timeoutMs?: number;
  responseType?: "json" | "blob";
}

async function requestIncidentAnalysis<T>(
  endpoint: string,
  init: IncidentAnalysisRequestOptions = {},
): Promise<T> {
  const {
    timeoutMs = DEFAULT_API_TIMEOUT_MS,
    responseType = "json",
    ...requestInit
  } = init;
  const requestSignal = createRequestSignal(requestInit.signal, timeoutMs);
  try {
    let response: Response;
    try {
      response = await fetch(`${INCIDENT_ANALYSIS_API_BASE}${endpoint}`, {
        ...requestInit,
        signal: requestSignal.signal,
      });
    } catch (error) {
      if (requestSignal.didTimeout()) {
        throw new IncidentAnalysisApiError(0, "The request timed out.", "timeout");
      }
      if (requestSignal.signal.aborted || isAbortError(error)) {
        throw new IncidentAnalysisApiError(0, "The request was cancelled.", "cancelled");
      }
      throw new IncidentAnalysisApiError(0, "Unable to reach Incident Analysis API", "network");
    }

    if (!response.ok) {
      const responseBody = await readResponseBody(response);
      const details = parseHttpError(response.status, responseBody.value);
      throw new IncidentAnalysisApiError(response.status, details.message, "http", details.field);
    }
    if (responseType === "blob") return await response.blob() as T;

    const responseBody = await readResponseBody(response);
    if (!responseBody.hasBody) return undefined as T;
    if (responseBody.isJson && !responseBody.isValidJson) {
      throw new IncidentAnalysisApiError(response.status, "Incident Analysis returned an invalid response.", "parse");
    }
    return responseBody.value as T;
  } finally {
    requestSignal.cleanup();
  }
}

export async function analyzeIncidents(
  csvFile: File | Blob,
  options: IncidentAnalysisRequestOptions = {},
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
      ...options,
      method: "POST",
      body: formData,
    }
  );
}

export async function exportIncidentResults(
  options: IncidentAnalysisRequestOptions = {},
): Promise<Blob> {
  const response = await requestIncidentAnalysis<Blob>(
    "/incidents/results/export",
    { ...options, responseType: "blob" },
  );
  return response;
}

export const analyzeIncidentCsv = analyzeIncidents;
export const downloadLatestIncidentResults = exportIncidentResults;
