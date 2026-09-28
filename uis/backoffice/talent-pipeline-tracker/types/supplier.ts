export const SUPPLIER_COUNTRIES = ["Spain", "USA"] as const;
export const SUPPLIER_CATEGORIES = [
  "job_boards",
  "ats_software",
  "assessment_tools",
  "training_platforms",
  "payroll_and_hr_software",
  "video_interview",
  "background_check",
  "office_and_facilities",
  "it_and_software_licenses",
] as const;
export const SUPPLIER_STATUSES = ["active", "suspended"] as const;

export type SupplierCountry = (typeof SUPPLIER_COUNTRIES)[number];
export type SupplierCategory = (typeof SUPPLIER_CATEGORIES)[number];
export type SupplierStatus = (typeof SUPPLIER_STATUSES)[number];

export interface Supplier {
  id: number;
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: "EUR" | "USD";
  updated_at: string;
  status: SupplierStatus;
  contract_renewal_date: string | null;
  contact_email: string | null;
  notes: string | null;
}

export interface SupplierCreatePayload {
  name: string;
  country: SupplierCountry;
  categories: SupplierCategory[];
  monthly_rate: number;
  currency: "EUR" | "USD";
  status: SupplierStatus;
  contract_renewal_date?: string;
  contact_email?: string;
  notes?: string;
}

export const SUPPLIER_CATEGORY_LABELS: Record<SupplierCategory, string> = {
  job_boards: "Job boards",
  ats_software: "ATS software",
  assessment_tools: "Assessment tools",
  training_platforms: "Training platforms",
  payroll_and_hr_software: "Payroll & HR software",
  video_interview: "Video interview",
  background_check: "Background check",
  office_and_facilities: "Office & facilities",
  it_and_software_licenses: "IT & software licenses",
};
