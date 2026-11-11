/** Business reporting response returned by GET /api/reporting/weekly-office-program-performance. */
export interface WeeklyBusinessPerformance {
  office: "Valencia" | "Miami";
  programme_id: string;
  week_start: string;
  total_material_cost: number | string;
  kits_delivered_count: number;
  shortage_events_count: number;
  cost_variance_events_count: number;
  currency: "EUR" | "USD";
  computed_at: string;
}

export interface BusinessReportingApiClient {
  request<T>(
    endpoint: string,
    options?: { auth?: boolean; method?: string; timeoutMs?: number },
  ): Promise<T>;
}