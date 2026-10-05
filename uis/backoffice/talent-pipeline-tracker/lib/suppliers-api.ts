import type {
  Supplier,
  SupplierCreatePayload,
  SupplierCategory,
  SupplierCountry,
  SupplierStatus,
} from "@/types/supplier";
import { nexovaApi } from "@/lib/nexova-api";
import type { NexovaRequestOptions } from "@/lib/nexova-api";

async function request<T>(
  endpoint: string,
  options: NexovaRequestOptions = {},
): Promise<T> {
  return nexovaApi.request<T>(endpoint, { ...options, auth: true });
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
    json: payload,
  });
}

export function updateSupplierRate(id: number, monthly_rate: number): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/rate`, {
    method: "PATCH",
    json: { monthly_rate },
  });
}

export function updateSupplierStatus(id: number, status: SupplierStatus): Promise<Supplier> {
  return request<Supplier>(`/suppliers/${id}/status`, {
    method: "PATCH",
    json: { status },
  });
}

export function deleteSupplier(id: number): Promise<void> {
  return request<void>(`/suppliers/${id}`, { method: "DELETE" });
}
