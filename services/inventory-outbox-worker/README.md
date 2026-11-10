# Inventory telemetry outbox worker

Small independent consumer for the Inventory transactional outbox. It uses the same `DATABASE_URL` as the API for claiming and updating local outbox rows, and `TELEMETRY_DATABASE_URL` for idempotent inserts into `public.telemetry_events`.

## Run

From `services/api`, using the API's existing uv environment:

```powershell
$env:PYTHONPATH = (Resolve-Path ..\..\packages\shared\python\src).Path + ';' + (Get-Location).Path
uv run python -m app.inventory_outbox_worker
```

Both database URLs must be set in the worker process. Never point it at a production inventory DB without an operational deployment/backup decision. Run the additive inventory migration before starting it; the worker does not create or migrate tables at startup.

Docker Compose defines this process as `inventory-outbox-worker`, built from this directory's Dockerfile. It uses the root `.env` like the backend; confirm `DATABASE_URL` targets the same inventory database as the API and `TELEMETRY_DATABASE_URL` targets the intended telemetry store. `depends_on` controls startup order only; it does not wait for database readiness. The worker retries recoverable failures.

## Delivery behavior

- Claims bounded batches using leases; PostgreSQL uses `FOR UPDATE SKIP LOCKED`, SQLite uses conditional atomic updates.
- Sends one event per repository call. Destination conflict on stable `event_id` is treated as successful idempotent delivery.
- Transient transport/server failures are retried with bounded exponential backoff and jitter; invalid/permanent payload/configuration failures go to `dead` immediately. Events reaching the configured attempt limit are dead-lettered. Correct the external configuration before manually re-queuing permanent failures.
- Leases allow another worker to recover events after a process crash. Delivery is at-least-once; the stable destination key suppresses duplicates.
- Old delivered/dead rows are purged only after the configurable retention period. Pending rows are never removed by retention.
- The worker accepts `inbound_order_created`, `outbound_order_created`, `stock_threshold_triggered`, and `kit_cost_variance_detected` Inventory events. Threshold events represent an outbound crossing from stock `>= threshold` to `< threshold`; kit-cost events use the weighted-average costs and preparation snapshot emitted by the inventory domain. Event dimensions are checked against the telemetry allowlists before durable insertion.
- Durable `last_error` stores the exception class only, not exception text that could expose connection details.

Environment variables: `OUTBOX_POLL_SECONDS` (default 2), `OUTBOX_BATCH_SIZE` (50), `OUTBOX_LEASE_SECONDS` (60), `OUTBOX_MAX_ATTEMPTS` (10), `OUTBOX_BACKOFF_BASE_SECONDS` (2), `OUTBOX_BACKOFF_MAX_SECONDS` (900), `OUTBOX_RETENTION_DAYS` (90), and `OUTBOX_JITTER_FRACTION` (0.2). Values are validated at startup.
