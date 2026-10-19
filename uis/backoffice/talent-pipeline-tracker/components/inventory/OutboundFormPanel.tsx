"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Button, Input, Select, Spinner } from "@/components/ui";
import { createOutbound, listProducts, inventoryErrorMessage } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import {
  INVENTORY_EXIT_TYPES,
  INVENTORY_OFFICE_OPTIONS,
  type AssetExitCreate,
  type AssetWithStock,
} from "@/types/inventory";

interface OutboundFormPanelProps {
  initialProductId?: string | null;
}

const EMPTY_FORM: AssetExitCreate = {
  asset_id: 0,
  quantity: 0,
  exit_type: "allocation",
  assigned_to: "",
  office: "Valencia",
};

const EXIT_TYPE_OPTIONS = INVENTORY_EXIT_TYPES.map((exitType) => ({
  value: exitType,
  label:
    exitType === "allocation"
      ? "Allocation (assign to a person)"
      : "Consumption (used up)",
}));

export function OutboundFormPanel({ initialProductId = null }: OutboundFormPanelProps) {
  const [products, setProducts] = useState<AssetWithStock[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productError, setProductError] = useState<string | null>(null);

  const [form, setForm] = useState<AssetExitCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{
    id: number;
    productName: string;
    quantity: number;
    exitType: AssetExitCreate["exit_type"];
  } | null>(null);

  const loadProducts = useCallback(async () => {
    setLoadingProducts(true);
    setProductError(null);
    try {
      const items = await listProducts(nexovaApi);
      setProducts(items);
      setForm((current) => {
        if (!initialProductId) return current;
        const preselected = items.find((p) => String(p.id) === initialProductId);
        if (!preselected) return current;
        if (current.asset_id !== 0) return current;
        return { ...current, asset_id: preselected.id };
      });
    } catch (requestError) {
      setProductError(
        inventoryErrorMessage(requestError, "No se pudieron cargar los productos.") ?? "",
      );
    } finally {
      setLoadingProducts(false);
    }
  }, [initialProductId]);

  // Synchronizes the form options with the external inventory API on mount.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadProducts(); }, [loadProducts]);

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === form.asset_id) ?? null,
    [products, form.asset_id],
  );

  const quantity = Number(form.quantity) || 0;
  const available = selectedProduct?.current_stock ?? 0;
  /** True when the client knows the requested quantity exceeds the available stock. */
  const insufficientStock =
    Boolean(selectedProduct) && quantity > 0 && quantity > available;
  const assigneeText = (form.assigned_to ?? "").trim();
  /** True when the form (in its current state) can be submitted. */
  const canSubmit =
    Boolean(selectedProduct) &&
    quantity > 0 &&
    !insufficientStock &&
    (form.exit_type === "consumption" || assigneeText !== "");

  function updateField<K extends keyof AssetExitCreate>(
    key: K,
    value: AssetExitCreate[K],
  ) {
    // Any edit on the form is a fresh movement: hide the previous confirmation
    // (and any stale error) so the success message only shows right after a
    // successful creation.
    setCreated(null);
    setError(null);
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateExitType(value: AssetExitCreate["exit_type"]) {
    setCreated(null);
    setError(null);
    setForm((current) => ({
      ...current,
      exit_type: value,
      // Switching to consumption drops the assignee; allocation keeps it.
      assigned_to: value === "consumption" ? "" : current.assigned_to,
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: AssetExitCreate = {
      ...form,
      quantity,
      assigned_to: form.exit_type === "consumption" ? null : assigneeText,
    } as AssetExitCreate;
    // Client-side guard: never send a request that would be rejected by stock.
    if (insufficientStock) return;
    setSaving(true);
    setError(null);
    setCreated(null);
    try {
      const createdOrder = await createOutbound(nexovaApi, payload);
      setCreated({
        id: createdOrder.id,
        productName: selectedProduct?.name ?? `product ${createdOrder.asset_id}`,
        quantity: payload.quantity,
        exitType: payload.exit_type,
      });
      // Reset only the form fields — the confirmation banner must stay visible.
      setForm({ ...EMPTY_FORM });
    } catch (requestError) {
      setError(
        inventoryErrorMessage(requestError, "No se pudo registrar la salida.") ?? "",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange">
          Nexova operations
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          Create outbound
        </h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Record a stock allocation (assigned to a person) or a consumption.
        </p>
      </div>

      <section className="mt-10">
        <form
          className="rounded-2xl border border-brand-lightgray bg-brand-white p-5 shadow-sm sm:p-6"
          onSubmit={submit}
        >
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="sm:col-span-2 lg:col-span-3">
              <Select
                label="Product"
                placeholder={
                  loadingProducts
                    ? "Loading products…"
                    : productError
                      ? "Products unavailable"
                      : "Select a product"
                }
                options={products.map((product) => ({
                  value: String(product.id),
                  label: `${product.name} (${product.sku})`,
                }))}
                value={form.asset_id ? String(form.asset_id) : ""}
                onChange={(event) =>
                  updateField("asset_id", Number(event.target.value))
                }
                disabled={loadingProducts || products.length === 0}
              />
              {productError && (
                <p role="alert" className="mt-1 text-xs text-red-600">
                  {productError}
                </p>
              )}
            </div>
            <Input
              label="Quantity"
              required
              min={1}
              step="1"
              type="number"
              value={form.quantity || ""}
              onChange={(event) =>
                updateField("quantity", Number(event.target.value))
              }
            />
            <Select
              label="Type of movement"
              options={EXIT_TYPE_OPTIONS}
              value={form.exit_type}
              onChange={(event) =>
                updateExitType(event.target.value as AssetExitCreate["exit_type"])
              }
            />
            <Select
              label="Office"
              options={INVENTORY_OFFICE_OPTIONS}
              value={form.office}
              onChange={(event) =>
                updateField("office", event.target.value as AssetExitCreate["office"])
              }
            />
            {form.exit_type === "allocation" && (
              <div className="sm:col-span-2 lg:col-span-3">
                <Input
                  label="Assigned to"
                  required
                  placeholder="e.g. María García"
                  value={form.assigned_to ?? ""}
                  onChange={(event) => updateField("assigned_to", event.target.value)}
                />
              </div>
            )}
          </div>

          {selectedProduct && (
            <p
              className={`mt-4 flex items-center gap-2 rounded-xl border px-4 py-3 text-sm ${
                available <= 1
                  ? "border-red-200 bg-red-50 text-red-800"
                  : available <= 7
                    ? "border-amber-200 bg-amber-50 text-amber-800"
                    : "border-green-200 bg-green-50 text-green-800"
              }`}
            >
              <span aria-hidden="true">📦</span>
              <span>
                Available stock for{" "}
                <span className="font-semibold">{selectedProduct.name}</span>:{" "}
                <span className="font-bold">{available} unit{available === 1 ? "" : "s"}</span>
              </span>
            </p>
          )}

          {insufficientStock && (
            <p
              role="alert"
              className="mt-4 flex items-start gap-2 rounded-xl border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800"
            >
              <span aria-hidden="true" className="font-black">⚠</span>
              <span>
                Only {available} unit{available === 1 ? "" : "s"} available for{" "}
                <span className="font-semibold">{selectedProduct?.name}</span>. Reduce the
                quantity to proceed.
              </span>
            </p>
          )}

          {error && (
            <p role="alert" className="mt-4 text-sm text-red-700">
              {error}
            </p>
          )}

          {created && (
            <div
              role="status"
              className="mt-4 flex items-start gap-3 rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800"
            >
              <span
                aria-hidden="true"
                className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-600 text-xs font-black text-white"
              >
                ✓
              </span>
              <div>
                <p className="font-bold">Outbound order #{created.id} created successfully.</p>
                <p className="mt-0.5 text-green-700">
                  {created.quantity} unit{created.quantity === 1 ? "" : "s"} of{" "}
                  {created.productName} removed from stock
                  {created.exitType === "allocation"
                    ? " and allocated."
                    : " (consumed)."}
                </p>
              </div>
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button
              type="submit"
              loading={saving}
              disabled={!canSubmit}
            >
              Create outbound
            </Button>
            <Link
              href="/inventory/products"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-brand-lightgray bg-brand-white px-5 py-2.5 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/50"
            >
              Back to current stock
            </Link>
          </div>
          {loadingProducts && (
            <div className="mt-4 flex items-center gap-2 text-sm text-brand-anthracite/60">
              <Spinner size="sm" /> Loading products…
            </div>
          )}
        </form>
      </section>
    </div>
  );
}