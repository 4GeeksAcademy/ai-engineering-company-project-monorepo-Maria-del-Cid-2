/**
 * Nexova inventory API integration layer.
 *
 * All HTTP calls to the protected `/api/inventory` endpoints are centralized
 * here. Components, hooks and pages must never call `fetch` directly — they
 * use these functions (or `nexovaApi.request` through them).
 *
 * Every request runs through `nexovaApi.request` with `auth: true`, which
 * reads the access token from localStorage (`nexova_access_token`) and sends
 * `Authorization: Bearer <token>`. Errors are never swallowed silently:
 * {@link inventoryErrorMessage} surfaces the API detail for 4xx/5xx responses
 * to the user.
 */

import { getUserFacingApiError } from "./api-error-messages.ts";
import { safeHttpFallback } from "./api-errors.ts";
import { NexovaApiError } from "./nexova-api.ts";
import type { NexovaApiClient } from "./nexova-api.ts";
import type {
  AssetEntryCreate,
  AssetExitCreate,
  AssetWithStock,
  InventoryOrder,
} from "../types/inventory.ts";

export { NexovaApiError };

export type {
  AssetEntry,
  AssetEntryCreate,
  AssetExit,
  AssetExitCreate,
  AssetWithStock,
  InventoryEntryOrder,
  InventoryExitOrder,
  InventoryExitType,
  InventoryOffice,
  InventoryOrder,
  StockLevel,
} from "../types/inventory";

export {
  INVENTORY_EXIT_TYPES,
  INVENTORY_EXIT_TYPE_LABELS,
  INVENTORY_OFFICE_LABELS,
  INVENTORY_OFFICES,
  INVENTORY_OFFICE_OPTIONS,
} from "../types/inventory.ts";

/** The subset of {@link NexovaApiClient} used by this layer. */
export type InventoryApiClient = Pick<NexovaApiClient, "request">;

function request<T>(
  client: InventoryApiClient,
  endpoint: string,
  options: Parameters<InventoryApiClient["request"]>[1] = {},
): Promise<T> {
  return client.request<T>(endpoint, { ...options, auth: true });
}

/** List every inventory product with its derived current stock. */
export function listProducts(client: InventoryApiClient): Promise<AssetWithStock[]> {
  return request<AssetWithStock[]>(client, "/inventory/products");
}

/** Load a single inventory product with its derived current stock. */
export function getProduct(
  client: InventoryApiClient,
  assetId: number,
): Promise<AssetWithStock> {
  return request<AssetWithStock>(client, `/inventory/products/${assetId}`);
}

/** List all receipt and consumption movements as a discriminated union. */
export function listOrders(client: InventoryApiClient): Promise<InventoryOrder[]> {
  return request<InventoryOrder[]>(client, "/inventory/orders");
}

/** Created inbound movement as returned by the API. */
export type InboundCreated = AssetEntryCreate & {
  id: number;
  created_at: string;
  user_uuid: string;
};

/** Created outbound movement as returned by the API. */
export type OutboundCreated = AssetExitCreate & {
  id: number;
  created_at: string;
  user_uuid: string;
};

/** Record one inbound movement (a received delivery). */
export function createInbound(
  client: InventoryApiClient,
  payload: AssetEntryCreate,
): Promise<InboundCreated> {
  return request<InboundCreated>(client, "/inventory/orders/inbound", {
    method: "POST",
    json: payload,
  });
}

/** Record one outbound movement (consumption or allocation). */
export function createOutbound(
  client: InventoryApiClient,
  payload: AssetExitCreate,
): Promise<OutboundCreated> {
  return request<OutboundCreated>(client, "/inventory/orders/outbound", {
    method: "POST",
    json: payload,
  });
}

/**
 * Build a user-facing message for an inventory API failure.
 *
 * For HTTP errors it prefers the API's own `detail` when it differs from the
 * generic fallback — this is what surfaces messages such as "Insufficient
 * stock for this outbound movement." or the 428 UUID precondition. Network,
 * timeout and 5xx errors use the stable localized messages from
 * `getUserFacingApiError`. Returns `null` for cancelled requests.
 */
export function inventoryErrorMessage(
  error: unknown,
  fallback: string,
): string | null {
  if (!(error instanceof NexovaApiError)) return fallback;
  if (error.kind === "cancelled") return null;
  if (error.kind !== "http") {
    return getUserFacingApiError(error, fallback);
  }

  if (error.status !== null && error.status >= 500) {
    return getUserFacingApiError(error, fallback);
  }

  const status = error.status ?? 0;
  const generic = safeHttpFallback(status);
  const detail = error.message?.trim();
  if (detail && detail !== generic) {
    return detail;
  }
  return getUserFacingApiError(error, fallback);
}