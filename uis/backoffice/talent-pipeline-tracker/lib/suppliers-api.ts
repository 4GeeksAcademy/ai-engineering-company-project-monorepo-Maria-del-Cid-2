import type {
  Supplier,
  SupplierCreatePayload,
  SupplierCategory,
  SupplierCountry,
  SupplierStatus,
} from "@/types/supplier";

const SUPPLIER_API_BASE =
  process.env.NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_BASE ?? "http://localhost:8000/api";

export class SupplierApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "SupplierApiError";
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return response.statusText || "Unknown API error";
  try {
    const parsed: unknown = JSON.parse(body);
    if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
      const detail = parsed.detail;
      if (typeof detail === "string") return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((item) => (typeof item === "object" && item !== null && "msg" in item ? String(item.msg) : String(item)))
          .join("; ");
      }
    }
  } catch {
    // Use the raw body below when the API did not return JSON.
  }
  return body;
}

async function request<T>(endpoint: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${SUPPLIER_API_BASE}${endpoint}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new SupplierApiError(0, "Unable to reach Supplier Directory API");
  }
  if (!response.ok) {
    throw new SupplierApiError(
      response.status,
      `Supplier Directory API error ${response.status}: ${await readErrorMessage(response)}`
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function listSuppliers(filters: {
  country?: SupplierCountry;
  category?: SupplierCategory;
} = {}): Promise<Supplier[]> {
  const params = new URLSearchParams();
  if (filters.country) params.set("country", filters.country);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return request<Supplier[]>(`/suppliers${query ? `?${query}` : ""}`);
}

export function createSupplier(payload: SupplierCreatePayload): Promise<Supplier> {
  return request<Supplier>("/suppliers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSupplierRate(id: number, monthly_rate: number): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/rate`, {
    method: "PATCH",
    body: JSON.stringify({ monthly_rate }),
  });
}

export function updateSupplierStatus(id: number, status: SupplierStatus): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function deleteSupplier(id: number): Promise<void> {
  return request<void>(`/suppliers/${id}`, { method: "DELETE" });
}
