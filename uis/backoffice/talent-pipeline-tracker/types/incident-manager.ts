export const INCIDENT_MANAGER_CATEGORIES = [
  "technical_failure",
  "process_error",
  "client_complaint",
  "candidate_issue",
  "staff_issue",
  "sla_breach",
  "data_quality",
  "other",
] as const;

export const INCIDENT_MANAGER_STATUSES = [
  "open",
  "in_progress",
  "resolved",
  "discarded",
] as const;

export const INCIDENT_MANAGER_ORIGINS = ["customer", "branch", "internal"] as const;

export const INCIDENT_MANAGER_BRANCHES = [
  "central",
  "valencia_operations",
  "miami_office",
  "remote",
] as const;

export type IncidentManagerCategory = (typeof INCIDENT_MANAGER_CATEGORIES)[number];
export type IncidentManagerStatus = (typeof INCIDENT_MANAGER_STATUSES)[number];
export type IncidentManagerOrigin = (typeof INCIDENT_MANAGER_ORIGINS)[number];
export type IncidentManagerBranch = (typeof INCIDENT_MANAGER_BRANCHES)[number];

export interface Incident {
  id: number;
  title: string;
  description: string;
  category: IncidentManagerCategory;
  status: IncidentManagerStatus;
  origin: IncidentManagerOrigin;
  branch: IncidentManagerBranch;
  created_at: string;
  updated_at: string;
}

export interface IncidentCreatePayload {
  title: string;
  description: string;
  category: IncidentManagerCategory;
  status: IncidentManagerStatus;
  origin: IncidentManagerOrigin;
  branch: IncidentManagerBranch;
}

export interface IncidentSummary {
  total: number;
  by_status: Record<IncidentManagerStatus, number>;
  by_category: Record<IncidentManagerCategory, number>;
  by_origin: Record<IncidentManagerOrigin, number>;
  by_branch: Record<IncidentManagerBranch, number>;
}

export const INCIDENT_MANAGER_CATEGORY_LABELS: Record<IncidentManagerCategory, string> = {
  technical_failure: "Technical failure",
  process_error: "Process error",
  client_complaint: "Client complaint",
  candidate_issue: "Candidate issue",
  staff_issue: "Staff issue",
  sla_breach: "SLA breach",
  data_quality: "Data quality",
  other: "Other",
};

export const INCIDENT_MANAGER_STATUS_LABELS: Record<IncidentManagerStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  discarded: "Discarded",
};

export const INCIDENT_MANAGER_ORIGIN_LABELS: Record<IncidentManagerOrigin, string> = {
  customer: "Customer",
  branch: "Branch",
  internal: "Internal",
};

export const INCIDENT_MANAGER_BRANCH_LABELS: Record<IncidentManagerBranch, string> = {
  central: "Central — Sede Valencia",
  valencia_operations: "Valencia — Operaciones",
  miami_office: "Miami Office",
  remote: "Remoto (empleado sin sede fija)",
};

export const INCIDENT_MANAGER_TRANSITIONS: Record<
  IncidentManagerStatus,
  readonly IncidentManagerStatus[]
> = {
  open: ["in_progress", "discarded"],
  in_progress: ["resolved", "discarded"],
  resolved: [],
  discarded: [],
};
