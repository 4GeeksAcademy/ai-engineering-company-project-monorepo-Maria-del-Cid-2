"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Button, Input, Select, Spinner } from "@/components/ui";
import { createInbound, listProducts, inventoryErrorMessage } from "@/lib/inventory";
import { nexovaApi } from "@/lib/nexova-api";
import {
  INVENTORY_OFFICE_OPTIONS,
  type AssetEntryCreate,
  type AssetWithStock,
} from "@/types/inventory";

interface InboundFormPanelProps {
  initialProductId?: string | null;
}

const EMPTY_FORM: AssetEntryCreate = {
  asset_id: 0,
  quantity: 0,
  supplier: "",
  office: "Valencia",
};

export function InboundFormPanel({ initialProductId = null }: InboundFormPanelProps) {
  const [products, setProducts] = useState<AssetWithStock[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productError, setProductError] = useState<string | null>(null);

  const [form, setForm] = useState<AssetEntryCreate>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{
    id: number;
    productName: string;
    quantity: number;
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

  function updateField<K extends keyof AssetEntryCreate>(
    key: K,
    value: AssetEntryCreate[K],
  ) {
    // Any edit on the form is a fresh entry: hide the previous confirmation
    // (and any stale error) so the success message only shows right after a
    // successful creation.
    setCreated(null);
    setError(null);
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setCreated(null);
    const payload: AssetEntryCreate = {
      ...form,
      quantity: Number(form.quantity),
    };
    try {
      const createdOrder = await createInbound(nexovaApi, payload);
      setCreated({
        id: createdOrder.id,
        productName: selectedProduct?.name ?? `product ${createdOrder.asset_id}`,
        quantity: payload.quantity,
      });
      // Reset only the form fields — the confirmation banner must stay visible.
      setForm({ ...EMPTY_FORM });
    } catch (requestError) {
      setError(
        inventoryErrorMessage(requestError, "No se pudo registrar la entrada.") ?? "",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-brand-orange-dark">
          Nexova operations
        </p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          Create inbound
        </h1>
        <p className="mt-3 text-sm leading-6 text-brand-anthracite/70">
          Record a received delivery of inventory products.
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
            <Input
              label="Supplier"
              required
              placeholder="e.g. Nexova Procurement"
              value={form.supplier}
              onChange={(event) => updateField("supplier", event.target.value)}
            />
            <Select
              label="Office"
              options={INVENTORY_OFFICE_OPTIONS}
              value={form.office}
              onChange={(event) =>
                updateField("office", event.target.value as AssetEntryCreate["office"])
              }
            />
          </div>

          {selectedProduct && (
            <p className="mt-4 text-sm text-brand-anthracite/70">
              Current stock for{" "}
              <span className="font-semibold">{selectedProduct.name}</span>:{" "}
              <span className="font-semibold">{selectedProduct.current_stock} unit{selectedProduct.current_stock === 1 ? "" : "s"}</span>
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
                <p className="font-bold">Inbound order #{created.id} created successfully.</p>
                <p className="mt-0.5 text-green-700">
                  {created.quantity} unit{created.quantity === 1 ? "" : "s"} of{" "}
                  {created.productName} added to stock.
                </p>
              </div>
            </div>
          )}

          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Button type="submit" loading={saving}>
              Create inbound
            </Button>
            <Link
              href="/inventory/products"
              className="inline-flex items-center justify-center gap-2 rounded-full border border-brand-lightgray bg-brand-white px-5 py-2.5 text-sm font-semibold text-brand-anthracite transition-colors hover:bg-brand-lightgray/50"
            >
              Back to current stock
            </Link>
          </div>
          {loadingProducts && (
            <div className="mt-4 flex items-center gap-2 text-sm text-brand-anthracite/65">
              <Spinner size="sm" /> Loading products…
            </div>
          )}
        </form>
      </section>
    </div>
  );
}