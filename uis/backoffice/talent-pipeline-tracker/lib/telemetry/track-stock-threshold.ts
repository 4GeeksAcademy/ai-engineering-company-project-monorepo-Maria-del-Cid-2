import { listProducts } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import { stockLevelFor, type AssetWithStock } from "@/types/inventory";
import type { TelemetryService } from "./telemetry-service.ts";

const STOCK_LEVEL_SEVERITY = {
  healthy: 0,
  low: 1,
  out: 2,
} as const;

export async function trackStockThresholdIfCrossed(
  telemetry: Pick<TelemetryService, "track">,
  previousProduct: AssetWithStock | null,
): Promise<AssetWithStock | null> {
  if (!previousProduct) return null;

  const previousLevel = stockLevelFor(previousProduct.current_stock);

  try {
    const updatedProduct = (await listProducts(nexovaApi)).find(
      (product) => product.id === previousProduct.id,
    );
    if (!updatedProduct) return null;

    const stockLevel = stockLevelFor(updatedProduct.current_stock);
    if (STOCK_LEVEL_SEVERITY[stockLevel] <= STOCK_LEVEL_SEVERITY[previousLevel]) {
      return updatedProduct;
    }

    telemetry.track("stock_threshold_triggered", {
      product_id: updatedProduct.id,
      product_sku: updatedProduct.sku,
      product_category: updatedProduct.category,
      office: updatedProduct.office,
      current_stock: updatedProduct.current_stock,
      threshold: stockLevel === "low" ? 8 : 2,
      stock_level: stockLevel,
    });
    return updatedProduct;
  } catch {
    console.warn("[Telemetry] Could not refresh stock after inventory movement.");
    return null;
  }
}