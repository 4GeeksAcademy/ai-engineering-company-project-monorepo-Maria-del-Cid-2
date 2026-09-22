export const INCIDENT_CATEGORIES = [
  "TECHNICAL",
  "BILLING",
  "ACCESS",
  "HR_QUERY",
  "COMPLAINT",
] as const;

export type IncidentCategory = (typeof INCIDENT_CATEGORIES)[number];

export const INCIDENT_STATUSES = ["OPEN", "CLOSED", "DISCARDED"] as const;

export type IncidentStatus = (typeof INCIDENT_STATUSES)[number];

export const VALIDATION_ERROR_CODES = [
  "missing_client_company",
  "invalid_category",
  "invalid_description",
  "invalid_agent_id",
  "invalid_email",
  "closed_without_satisfaction_score",
  "satisfaction_score_out_of_range",
] as const;

export type ValidationErrorCode = (typeof VALIDATION_ERROR_CODES)[number];

export type SatisfactionScore = 1 | 2 | 3 | 4 | 5;

export interface IncidentAnalysisResult {
  total_records: number;
  valid_records: number;
  invalid_records: number;
  by_category: Partial<Record<IncidentCategory, number>>;
  by_status: Partial<Record<IncidentStatus, number>>;
  satisfaction_distribution: Partial<Record<SatisfactionScore, number>>;
  average_satisfaction: number | null;
  invalid_by_type: Partial<Record<ValidationErrorCode, number>>;
}

export class IncidentAnalysisApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "IncidentAnalysisApiError";
    this.status = status;
  }
}
