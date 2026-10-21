"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Spinner } from "@/components/ui";
import { inventoryErrorMessage, listProducts } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import {
  STOCK_LEVEL_LABELS,
  stockLevelFor,
  type AssetWithStock,
  type StockLevel,
} from "@/types/inventory";

/**
 * Visual stock levels. Thresholds confirmed with the product owner.
 *
 * - **Healthy (green)** badge: 8 or more units.
 * - **Low (amber)** badge: between 2 and 7 units (inclusive).
 * - **Out of stock (red)** badge: 1 or 0 units.
 */
const STOCK_BADGE_CLASSES: Record<StockLevel, string> = {
  healthy: "bg-green-100 text-green-800",
  low: "bg-orange-100 text-orange-800",
  out: "bg-red-100 text-red-800",
};

const STOCK_AVATAR_CLASSES: Record<StockLevel, string> = {
  healthy: "bg-green-100 text-green-800",
  low: "bg-orange-100 text-orange-800",
  out: "bg-red-100 text-red-800",
};

function StockBadge({ level, stock }: { level: StockLevel; stock: number }) {
  return (
    <Badge className={STOCK_BADGE_CLASSES[level]}>
      {STOCK_LEVEL_LABELS[level]} · {stock} unit{stock === 1 ? "" : "s"}
    </Badge>
  );
}

function ProductRow({ product }: { product: AssetWithStock }) {
  const level = stockLevelFor(product.current_stock);
  const inboundLink = `/inventory/orders/inbound?product=${product.id}`;
  const outboundLink = `/inventory/orders/outbound?product=${product.id}`;

  return (
    <article className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-4">
          <span
            className={`mt-0.5 inline-flex h-14 w-14 shrink-0 flex-col items-center justify-center gap-0.5 rounded-xl leading-none ${STOCK_AVATAR_CLASSES[level]}`}
            aria-hidden="true"
          >
            <span className="text-base font-black">{product.current_stock}</span>
            <span className="text-[10px] font-bold uppercase tracking-wide opacity-80">
              units
            </span>
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-black">{product.name}</h3>
              <StockBadge level={level} stock={product.current_stock} />
            </div>
            <p className="mt-1 text-sm text-brand-anthracite/65">
              <span className="font-semibold">{product.sku}</span>
              {" · "}
              {product.category}
              {" · "}
              {product.office}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col gap-2 sm:w-44">
          <Link
            href={inboundLink}
            className="inline-flex items-center justify-center gap-2 rounded-full border border-brand-lightgray bg-brand-white px-4 py-2 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/50"
          >
            Create inbound
          </Link>
          <Link
            href={outboundLink}
            className="inline-flex items-center justify-center gap-2 rounded-full border border-brand-lightgray bg-brand-white px-4 py-2 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/50"
          >
            Create outbound
          </Link>
        </div>
      </div>
    </article>
  );
}

export function InventoryCurrentStockPanel() {
  const [products, setProducts] = useState<AssetWithStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProducts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProducts(await listProducts(nexovaApi));
    } catch (requestError) {
      setError(inventoryErrorMessage(requestError, "No se pudo cargar el stock actual.") ?? "");
    } finally {
      setLoading(false);
    }
  }, []);

  // Synchronizes the panel with the external inventory API on mount.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadProducts(); }, [loadProducts]);

  const totalUnits = useMemo(
    () => products.reduce((sum, product) => sum + product.current_stock, 0),
    [products],
  );

  const emptyLabel =
    "No inventory products have been recorded yet. Create an inbound movement to record stock.";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange-dark">
          Nexova operations
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          Current Stock
        </h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Inventory products with their derived stock. Green means 8 or more
          units, amber means between 2 and 7, and red means 1 or none.
        </p>
      </div>

      <section className="mt-10">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange-dark">
              Assets
            </p>
            <h2 className="mt-1 text-xl font-black">
              {products.length} product{products.length === 1 ? "" : "s"} ·{" "}
              {totalUnits} unit{totalUnits === 1 ? "" : "s"} in total
            </h2>
          </div>
          {loading && <Spinner size="sm" />}
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
          >
            {error}
          </div>
        )}

        {!loading && !error && products.length === 0 && (
          <p className="mt-5 rounded-2xl border border-dashed border-brand-lightgray p-8 text-center text-sm text-brand-anthracite/65">
            {emptyLabel}
          </p>
        )}

        {!loading && products.length > 0 && (
          <div className="mt-5 space-y-4">
            {products.map((product) => (
              <ProductRow key={product.id} product={product} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}