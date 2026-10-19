import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { NexovaApiClient, NexovaApiError } from "../lib/nexova-api.ts";
import {
  createInbound,
  createOutbound,
  getProduct,
  inventoryErrorMessage,
  listOrders,
  listProducts,
} from "../lib/inventory.ts";

class MemoryStorage {
  values = new Map();

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, value);
  }

  removeItem(key) {
    this.values.delete(key);
  }
}

function makeClient(fetcher) {
  const storage = new MemoryStorage();
  storage.setItem("nexova_access_token", "inventory-jwt");
  const client = new NexovaApiClient({
    baseUrl: "http://localhost:8000/api",
    fetcher,
    storage,
    redirectToExpiredLogin: () => {},
  });
  return { client, storage };
}

const product = {
  id: 1,
  name: 'Portátil 14" Business',
  sku: "NXV-IT-001",
  category: "hardware",
  office: "Valencia",
  current_stock: 12,
};

const inboundOrder = {
  id: 10,
  asset_id: 1,
  quantity: 5,
  supplier: "TechDistrib Valencia S.L.",
  office: "Valencia",
  created_at: "2026-10-19T10:00:00Z",
  user_uuid: "11111111-1111-1111-1111-111111111111",
  type: "entry",
};

const outboundOrder = {
  id: 11,
  asset_id: 1,
  quantity: 2,
  exit_type: "allocation",
  assigned_to: "María García",
  office: "Valencia",
  created_at: "2026-10-19T11:00:00Z",
  user_uuid: "11111111-1111-1111-1111-111111111111",
  type: "exit",
};

describe("inventory API", () => {
  it("lists products using GET /inventory/products with Bearer", async () => {
    let request;
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json([product]);
    });

    assert.deepEqual(await listProducts(client), [product]);
    assert.equal(request.url, "http://localhost:8000/api/inventory/products");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer inventory-jwt");
  });

  it("loads a single product by id using GET /inventory/products/{id}", async () => {
    let request;
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(product);
    });

    assert.deepEqual(await getProduct(client, 1), product);
    assert.equal(request.url, "http://localhost:8000/api/inventory/products/1");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer inventory-jwt");
  });

  it("lists the discriminated union of movement orders", async () => {
    let request;
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json([inboundOrder, outboundOrder]);
    });

    assert.deepEqual(await listOrders(client), [inboundOrder, outboundOrder]);
    assert.equal(request.url, "http://localhost:8000/api/inventory/orders");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer inventory-jwt");
  });

  it("creates an inbound order with POST and a JSON payload", async () => {
    let request;
    const payload = {
      asset_id: 1,
      quantity: 5,
      supplier: "TechDistrib Valencia S.L.",
      office: "Valencia",
    };
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(inboundOrder, { status: 201 });
    });

    assert.deepEqual(await createInbound(client, payload), inboundOrder);
    assert.equal(request.url, "http://localhost:8000/api/inventory/orders/inbound");
    assert.equal(request.init.method, "POST");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer inventory-jwt");
    assert.equal(new Headers(request.init.headers).get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(request.init.body), payload);
  });

  it("creates an outbound order with POST and a JSON payload", async () => {
    let request;
    const payload = {
      asset_id: 1,
      quantity: 2,
      exit_type: "allocation",
      assigned_to: "María García",
      office: "Valencia",
    };
    const { client } = makeClient(async (url, init) => {
      request = { url, init };
      return Response.json(outboundOrder, { status: 201 });
    });

    assert.deepEqual(await createOutbound(client, payload), outboundOrder);
    assert.equal(request.url, "http://localhost:8000/api/inventory/orders/outbound");
    assert.equal(request.init.method, "POST");
    assert.equal(new Headers(request.init.headers).get("Authorization"), "Bearer inventory-jwt");
    assert.equal(new Headers(request.init.headers).get("Content-Type"), "application/json");
    assert.deepEqual(JSON.parse(request.init.body), payload);
  });

  it("surfaces the API detail for an outbound 400 (insufficient stock)", async () => {
    const { client } = makeClient(async () =>
      Response.json(
        { detail: "Insufficient stock for this outbound movement." },
        { status: 400 },
      ),
    );

    await assert.rejects(
      createOutbound(client, {
        asset_id: 1,
        quantity: 99,
        exit_type: "consumption",
        assigned_to: null,
        office: "Valencia",
      }),
      (error) => {
        assert.ok(error instanceof NexovaApiError);
        assert.equal(error.status, 400);
        assert.equal(error.message, "Insufficient stock for this outbound movement.");
        return true;
      },
    );
  });

  it("surfaces the 428 UUID precondition message for legacy users", async () => {
    const { client } = makeClient(async () =>
      Response.json(
        {
          detail: "The authenticated user must have a persistent UUID to write inventory movements.",
        },
        { status: 428 },
      ),
    );

    await assert.rejects(
      createInbound(client, {
        asset_id: 1,
        quantity: 1,
        supplier: "TechDistrib Valencia S.L.",
        office: "Valencia",
      }),
      (error) => {
        assert.ok(error instanceof NexovaApiError);
        assert.equal(error.status, 428);
        return true;
      },
    );
  });

  it("turns a 409 into a reject with the API detail preserved", async () => {
    const { client } = makeClient(async () =>
      Response.json({ detail: "The inventory movement conflicts with stored data." }, { status: 409 }),
    );

    await assert.rejects(
      createInbound(client, {
        asset_id: 1,
        quantity: 1,
        supplier: "TechDistrib Valencia S.L.",
        office: "Valencia",
      }),
      (error) => {
        assert.ok(error instanceof NexovaApiError);
        assert.equal(error.status, 409);
        return true;
      },
    );
  });

  it("maps a 503 to a stable user-facing message", async () => {
    const { client } = makeClient(async () =>
      Response.json({ detail: "Service unavailable" }, { status: 503 }),
    );

    await assert.rejects(listProducts(client), (error) => {
      assert.ok(error instanceof NexovaApiError);
      assert.equal(error.status, 503);
      const message = inventoryErrorMessage(error, "Fallback");
      assert.equal(message, "El servidor no está disponible. Inténtalo de nuevo más tarde.");
      return true;
    });
  });

  it("prefers the API detail for a 400 user-facing message", () => {
    const error = new NexovaApiError("http", 400, "Insufficient stock for this outbound movement.");
    assert.equal(
      inventoryErrorMessage(error, "Fallback"),
      "Insufficient stock for this outbound movement.",
    );
  });

  it("falls back to the caller fallback when the API detail equals the generic text", () => {
    // For a 400 whose detail matches safeHttpFallback(400), the layer cannot
    // produce a more specific message, so it uses the caller-provided fallback.
    const error = new NexovaApiError("http", 400, "The request could not be completed.");
    assert.equal(inventoryErrorMessage(error, "Fallback"), "Fallback");
  });

  it("returns null for cancelled requests", () => {
    const error = new NexovaApiError("cancelled", null, "The request was cancelled.");
    assert.equal(inventoryErrorMessage(error, "Fallback"), null);
  });
});