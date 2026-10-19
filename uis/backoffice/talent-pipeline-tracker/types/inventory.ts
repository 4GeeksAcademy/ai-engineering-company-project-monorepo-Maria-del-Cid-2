/**
 * Domain types for the Nexova inventory module.
 *
 * The vocabulary mirrors the API contract in `services/api/app/inventory`
 * (schemas.py) and the seed data (`services/api/app/inventory/seed.py`):
 *
 * - **Asset** is the inventory product: `name`, `sku`, `category` and
 *   `office`. Stock is not persisted — the API derives `current_stock` from
 *   the sum of inbound movements minus outbound movements.
 * - **Inbound** (`type: "entry"`) records a received delivery attributed to
 *   `supplier` and received at an `office`.
 * - **Outbound** (`type: "exit"`) records a consumption or allocation:
 *   `allocation` requires `assigned_to`; `consumption` must not have one.
 *
 * Offices follow the seed data: Nexova operates in Valencia and Miami.
 */

export const INVENTORY_OFFICES = ["Valencia", "Miami"] as const;
export type InventoryOffice = (typeof INVENTORY_OFFICES)[number];

export const INVENTORY_EXIT_TYPES = ["allocation", "consumption"] as const;
export type InventoryExitType = (typeof INVENTORY_EXIT_TYPES)[number];

/** Current stock levels. Thresholds documented in {@link stockLevelFor}. */
export type StockLevel = "healthy" | "low" | "out";

/**
 * Classify a current stock value against the confirmed thresholds:
 *
 * - `healthy` (**green**): 8 or more units.
 * - `low` (**amber**): between 2 and 7 units (inclusive).
 * - `out` (**red**): 1 or 0 units (below 2).
 */
export function stockLevelFor(currentStock: number): StockLevel {
  if (currentStock >= 8) return "healthy";
  if (currentStock >= 2) return "low";
  return "out";
}

export const STOCK_LEVEL_LABELS: Record<StockLevel, string> = {
  healthy: "Healthy",
  low: "Low",
  out: "Out of stock",
};

/** An inventory product with its derived current stock. */
export interface AssetWithStock {
  id: number;
  name: string;
  sku: string;
  category: string;
  office: string;
  current_stock: number;
}

/** Payload to create an inbound movement (a received delivery). */
export interface AssetEntryCreate {
  asset_id: number;
  quantity: number;
  supplier: string;
  office: string;
}

/** A created inbound movement as returned by the API. */
export interface AssetEntry extends AssetEntryCreate {
  id: number;
  created_at: string;
  user_uuid: string;
}

/** Payload to create an outbound movement (consumption or allocation). */
export interface AssetExitCreate {
  asset_id: number;
  quantity: number;
  exit_type: InventoryExitType;
  assigned_to: string | null;
  office: string;
}

/** A created outbound movement as returned by the API. */
export interface AssetExit extends AssetExitCreate {
  id: number;
  created_at: string;
  user_uuid: string;
}

/** Entry variant of the unified movement list. */
export interface InventoryEntryOrder extends AssetEntry {
  type: "entry";
}

/** Exit variant of the unified movement list. */
export interface InventoryExitOrder extends AssetExit {
  type: "exit";
}

/** Discriminated union returned by GET /inventory/orders. */
export type InventoryOrder = InventoryEntryOrder | InventoryExitOrder;

export const INVENTORY_EXIT_TYPE_LABELS: Record<InventoryExitType, string> = {
  allocation: "Allocation",
  consumption: "Consumption",
};

export const INVENTORY_OFFICE_LABELS: Record<InventoryOffice, string> = {
  Valencia: "Valencia",
  Miami: "Miami",
};

export const INVENTORY_OFFICE_OPTIONS: { value: InventoryOffice; label: string }[] =
  INVENTORY_OFFICES.map((office) => ({ value: office, label: office }));