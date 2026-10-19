"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Spinner } from "@/components/ui";
import { inventoryErrorMessage, listOrders, listProducts } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import {
  INVENTORY_EXIT_TYPE_LABELS,
  type AssetWithStock,
  type InventoryEntryOrder,
  type InventoryExitOrder,
  type InventoryOrder,
} from "@/types/inventory";

const ORDER_TYPE_CLASSES: Record<
  InventoryOrder["type"],
  { badge: string; label: string }
> = {
  entry: { badge: "bg-green-100 text-green-800", label: "Inbound" },
  exit: { badge: "bg-orange-100 text-orange-800", label: "Outbound" },
};

/** Abbreviate a creator UUID for display, e.g. `a1b2c3d4…`. */
function shortUuid(uuid: string): string {
  return uuid.length > 8 ? `${uuid.slice(0, 8)}…` : uuid;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function EntryDetail({ order }: { order: InventoryEntryOrder }) {
  return (
    <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-brand-anthracite/65">
      <div>
        <dt className="inline font-semibold">Supplier:</dt>{" "}
        <dd className="inline">{order.supplier}</dd>
      </div>
      <div>
        <dt className="inline font-semibold">Office:</dt>{" "}
        <dd className="inline">{order.office}</dd>
      </div>
    </dl>
  );
}

function ExitDetail({ order }: { order: InventoryExitOrder }) {
  return (
    <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-brand-anthracite/65">
      <div>
        <dt className="inline font-semibold">Type:</dt>{" "}
        <dd className="inline">{INVENTORY_EXIT_TYPE_LABELS[order.exit_type]}</dd>
      </div>
      <div>
        <dt className="inline font-semibold">Office:</dt>{" "}
        <dd className="inline">{order.office}</dd>
      </div>
      {order.assigned_to ? (
        <div>
          <dt className="inline font-semibold">Assigned to:</dt>{" "}
          <dd className="inline">{order.assigned_to}</dd>
        </div>
      ) : null}
    </dl>
  );
}

function OrderRow({
  order,
  productName,
}: {
  order: InventoryOrder;
  productName: string | null;
}) {
  const typeInfo = ORDER_TYPE_CLASSES[order.type];

  return (
    <article className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={typeInfo.badge}>{typeInfo.label}</Badge>
            <h3 className="text-lg font-black">{productName ?? `Product #${order.asset_id}`}</h3>
          </div>
          <p className="mt-1 text-sm text-brand-anthracite/60">
            <span className="font-mono text-xs">#{order.id}</span>
            <span className="mx-1.5">·</span>
            {order.quantity} unit{order.quantity === 1 ? "" : "s"}
          </p>
          {order.type === "entry" ? (
            <EntryDetail order={order} />
          ) : (
            <ExitDetail order={order} />
          )}
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <p className="text-sm font-semibold text-brand-anthracite">
            <span className="mr-1.5 text-xs font-bold uppercase tracking-wide text-brand-anthracite/50">
              Created by
            </span>
            <span className="font-mono" title={`User ${order.user_uuid}`}>
              {shortUuid(order.user_uuid)}
            </span>
          </p>
          <p className="mt-0.5 text-xs text-brand-anthracite/60" title={order.created_at}>
            {formatDate(order.created_at)}
          </p>
        </div>
      </div>
    </article>
  );
}

export function OrdersHistoryPanel() {
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [products, setProducts] = useState<AssetWithStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [orderList, productList] = await Promise.all([
        listOrders(nexovaApi),
        listProducts(nexovaApi),
      ]);
      setOrders(orderList);
      setProducts(productList);
    } catch (requestError) {
      setError(inventoryErrorMessage(requestError, "No se pudo cargar el historial de órdenes.") ?? "");
    } finally {
      setLoading(false);
    }
  }, []);

  // Synchronizes the panel with the external inventory API on mount.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadOrders(); }, [loadOrders]);

  const productNames = useMemo(() => {
    const map = new Map<number, string>();
    for (const product of products) map.set(product.id, product.name);
    return map;
  }, [products]);

  const emptyLabel =
    "No inbound or outbound movements have been recorded yet.";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          Nexova operations
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          Order History
        </h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Every inbound and outbound movement that has been recorded, newest
          first. Product names come from the current catalog; the creator is
          shown as an abbreviated user identifier (hover for the full one).
        </p>
      </div>

      <section className="mt-10">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
              Movements
            </p>
            <h2 className="mt-1 text-xl font-black">
              {orders.length} order{orders.length === 1 ? "" : "s"} recorded
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

        {!loading && !error && orders.length === 0 && (
          <p className="mt-5 rounded-2xl border border-dashed border-brand-lightgray p-8 text-center text-sm text-brand-anthracite/60">
            {emptyLabel}
          </p>
        )}

        {!loading && orders.length > 0 && (
          <div className="mt-5 space-y-4">
            {orders.map((order) => (
              <OrderRow
                key={`${order.type}-${order.id}`}
                order={order}
                productName={productNames.get(order.asset_id) ?? null}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}