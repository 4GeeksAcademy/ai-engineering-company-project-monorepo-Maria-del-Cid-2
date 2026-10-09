import { nexovaApi, NexovaApiError } from "@/lib/nexova-api";
import type {
  Incident,
  IncidentCreatePayload,
  IncidentManagerBranch,
  IncidentManagerCategory,
  IncidentManagerOrigin,
  IncidentManagerStatus,
  IncidentSummary,
} from "@/types/incident-manager";

export interface IncidentFilters {
  status?: IncidentManagerStatus;
  origin?: IncidentManagerOrigin;
  branch?: IncidentManagerBranch;
  category?: IncidentManagerCategory;
}

export function listIncidents(filters: IncidentFilters = {}): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.origin) params.set("origin", filters.origin);
  if (filters.branch) params.set("branch", filters.branch);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return nexovaApi.request<Incident[]>(`/incidents${query ? `?${query}` : ""}`, { auth: true });
}

export function createIncident(payload: IncidentCreatePayload): Promise<Incident> {
  return nexovaApi.request<Incident>("/incidents", {
    method: "POST",
    auth: true,
    json: payload,
  });
}

export function updateIncidentStatus(
  id: number,
  status: IncidentManagerStatus,
): Promise<Incident> {
  return nexovaApi.request<Incident>(`/incidents/${id}/status`, {
    method: "PATCH",
    auth: true,
    json: { status },
  });
}

export function getIncidentSummary(): Promise<IncidentSummary> {
  return nexovaApi.request<IncidentSummary>("/incidents/summary", { auth: true });
}

export function getIncidentErrorMessage(error: unknown): string {
  if (error instanceof NexovaApiError) {
    if (error.kind === "network" || error.isServerError) {
      return "Unable to reach the incidents service. Please try again.";
    }
    if (error.status === 401 || error.status === 403) {
      return "You are not authorized to manage incidents.";
    }
    return error.message || "Unable to complete the incident request.";
  }
  return "Unable to complete the incident request.";
}

export function getIncidentFieldError(error: unknown): string | null {
  if (error instanceof NexovaApiError && error.field) return error.message;
  return null;
}

export function isIncidentApiError(error: unknown): error is NexovaApiError {
  return error instanceof NexovaApiError;
}

export type IncidentCategory = IncidentManagerCategory;
