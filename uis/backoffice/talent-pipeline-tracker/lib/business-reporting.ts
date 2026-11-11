import type {
  BusinessReportingApiClient,
  WeeklyBusinessPerformance,
} from "../types/business-reporting.ts";

const WEEKLY_PERFORMANCE_ENDPOINT = "/reporting/weekly-office-program-performance";

export interface WeeklyBusinessPerformanceQuery {
  week_start?: string;
}

/** Fetch persisted weekly KPI rows using the authenticated Nexova API client. */
export function getWeeklyBusinessPerformance(
  client: BusinessReportingApiClient,
  query: WeeklyBusinessPerformanceQuery = {},
): Promise<WeeklyBusinessPerformance[]> {
  const search = new URLSearchParams();
  if (query.week_start) search.set("week_start", query.week_start);
  const suffix = search.size > 0 ? `?${search.toString()}` : "";

  return client.request<WeeklyBusinessPerformance[]>(
    `${WEEKLY_PERFORMANCE_ENDPOINT}${suffix}`,
    { auth: true },
  );
}