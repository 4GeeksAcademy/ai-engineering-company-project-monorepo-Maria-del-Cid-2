"""Unit tests for durable Inventory outbox delivery and lease handling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.inventory.migrate_programmes import migrate_programmes
from app.inventory.models import TelemetryOutboxEvent
from app.inventory_outbox_worker import (
    WorkerSettings,
    _claim_batch,
    _retry_delay,
    deliver_batch,
    purge_terminal_events,
)
from app.telemetry.repository import TelemetryStorageUnavailable


NOW = datetime(2025, 2, 1, tzinfo=timezone.utc)


class FakeTelemetryRepository:
    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.records = []

    def insert_many(self, records):
        self.records.extend(records)
        if self.outcome == "transient":
            raise TelemetryStorageUnavailable("persistence failed") from OSError("offline")
        if self.outcome == "missing_config":
            raise TelemetryStorageUnavailable("not configured")
        if self.outcome == "invalid_payload":
            raise ValueError("invalid")
        # A zero count means an event_id duplicate was already stored.
        return 0 if self.outcome == "duplicate" else len(records)


class InventoryOutboxWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        path = Path(self.tempdir.name) / "outbox.sqlite3"
        self.engine = create_engine(f"sqlite:///{path}")
        SQLModel.metadata.create_all(self.engine)
        self.settings = WorkerSettings(
            poll_seconds=1,
            batch_size=10,
            lease_seconds=30,
            max_attempts=2,
            backoff_base_seconds=2,
            backoff_max_seconds=10,
            retention_days=5,
            jitter_fraction=0,
        )

    def tearDown(self) -> None:
        self.engine.dispose()
        self.tempdir.cleanup()

    def add_event(self, *, event_id: str = "event-1", event_type: str = "inbound_order_created",
                  tags: dict | None = None, **kwargs) -> TelemetryOutboxEvent:
        default_tags = {
            "product_id": 7,
            "product_sku": "SKU-7",
            "product_category": "equipment",
            "programme_id": "programme-1",
            "quantity": 2,
            "supplier": "supplier",
            "office": "Valencia",
            "currency": "EUR",
            "unit_cost": 4.5,
            "user_uuid": "00000000-0000-0000-0000-000000000001",
        }
        values = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": NOW,
            "source": "/nexova/inventory",
            "tags": default_tags if tags is None else tags,
            "movement_type": "entry",
            "movement_id": 1,
            "available_at": NOW,
            **kwargs,
        }
        row = TelemetryOutboxEvent(**values)
        with Session(self.engine) as session:
            session.add(row)
            session.commit()
        return row

    def get_event(self, event_id: str = "event-1") -> TelemetryOutboxEvent:
        with Session(self.engine) as session:
            return session.exec(
                select(TelemetryOutboxEvent).where(TelemetryOutboxEvent.event_id == event_id)
            ).one()

    def test_claim_respects_available_at_and_recovers_expired_lease(self) -> None:
        self.add_event()
        claimed = _claim_batch(self.engine, self.settings, NOW)
        self.assertEqual(len(claimed), 1)
        self.assertTrue(claimed[0].lease_token)
        first_lease_token = claimed[0].lease_token
        self.assertEqual(_claim_batch(self.engine, self.settings, NOW), [])

        reclaimed = _claim_batch(self.engine, self.settings, NOW + timedelta(seconds=31))
        self.assertEqual(len(reclaimed), 1)
        self.assertNotEqual(reclaimed[0].lease_token, first_lease_token)

    def test_success_and_duplicate_are_both_acknowledged(self) -> None:
        for outcome in ("ok", "duplicate"):
            event_id = f"event-{outcome}"
            self.add_event(event_id=event_id)
            stats = deliver_batch(self.engine, FakeTelemetryRepository(outcome), self.settings, now=NOW)
            self.assertEqual(stats["delivered"], 1)
            row = self.get_event(event_id)
            self.assertEqual(row.status, "delivered")
            self.assertIsNotNone(row.delivered_at)
            self.assertIsNone(row.lease_token)

    def test_transient_failure_schedules_retry_then_dead_letters_at_limit(self) -> None:
        self.add_event()
        repo = FakeTelemetryRepository("transient")
        first = deliver_batch(self.engine, repo, self.settings, now=NOW)
        row = self.get_event()
        self.assertEqual(first["retried"], 1)
        self.assertEqual(row.attempt_count, 1)
        self.assertEqual(row.available_at, NOW + timedelta(seconds=2))
        self.assertEqual(row.last_error, "TelemetryStorageUnavailable")

        second = deliver_batch(self.engine, repo, self.settings, now=row.available_at)
        row = self.get_event()
        self.assertEqual(second["dead"], 1)
        self.assertEqual(row.status, "dead")
        self.assertEqual(row.attempt_count, 2)

    def test_expired_lease_at_attempt_limit_is_not_reclaimed(self) -> None:
        self.add_event(attempt_count=2, locked_until=NOW - timedelta(seconds=1))
        self.assertEqual(_claim_batch(self.engine, self.settings, NOW), [])

    def test_permanent_failure_goes_dead_and_does_not_leak_exception_text(self) -> None:
        self.add_event()
        stats = deliver_batch(
            self.engine, FakeTelemetryRepository("missing_config"), self.settings, now=NOW
        )
        row = self.get_event()
        self.assertEqual(stats["dead"], 1)
        self.assertEqual(row.status, "dead")
        self.assertNotIn("not configured", row.last_error or "")

    def test_invalid_payload_is_dead_lettered(self) -> None:
        self.add_event(event_type="unsupported_event")
        stats = deliver_batch(self.engine, FakeTelemetryRepository(), self.settings, now=NOW)
        self.assertEqual(stats["dead"], 1)
        self.assertEqual(self.get_event().status, "dead")

    def test_purge_deletes_only_expired_terminal_events(self) -> None:
        old = NOW - timedelta(days=6)
        self.add_event(event_id="delivered", status="delivered", delivered_at=old)
        self.add_event(event_id="dead", status="dead", dead_lettered_at=old)
        self.add_event(event_id="pending", available_at=old)
        deleted = purge_terminal_events(self.engine, 5, now=NOW)
        self.assertEqual(deleted, 2)
        with Session(self.engine) as session:
            remaining = {row.event_id for row in session.exec(select(TelemetryOutboxEvent)).all()}
        self.assertEqual(remaining, {"pending"})

    def test_backoff_is_bounded_and_settings_reject_invalid_values(self) -> None:
        self.assertEqual(_retry_delay(10_000, self.settings, random_value=1), 10)
        with self.assertRaises(ValueError):
            WorkerSettings(batch_size=0)
        with patch.dict("os.environ", {"OUTBOX_BATCH_SIZE": "0"}):
            with self.assertRaises(ValueError):
                WorkerSettings.from_env()

    def test_migration_adds_worker_columns_and_index_idempotently(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("DROP TABLE telemetry_outbox"))
            connection.execute(text("DROP TABLE programmes"))
            for table in ("asset_entries", "asset_exits", "assets"):
                connection.execute(text(f"DROP TABLE {table}"))
            connection.execute(text(
                "CREATE TABLE assets (id INTEGER PRIMARY KEY, name VARCHAR NOT NULL, "
                "sku VARCHAR NOT NULL, category VARCHAR NOT NULL, office VARCHAR NOT NULL)"
            ))
            connection.execute(text(
                "CREATE TABLE asset_entries (id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, "
                "quantity FLOAT NOT NULL, supplier VARCHAR NOT NULL, office VARCHAR NOT NULL, "
                "created_at TIMESTAMP NOT NULL, user_uuid CHAR(32) NOT NULL)"
            ))
            connection.execute(text(
                "CREATE TABLE asset_exits (id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, "
                "quantity FLOAT NOT NULL, exit_type VARCHAR NOT NULL, assigned_to VARCHAR, "
                "office VARCHAR NOT NULL, created_at TIMESTAMP NOT NULL, user_uuid CHAR(32) NOT NULL)"
            ))
            connection.execute(text(
                "INSERT INTO assets (id, name, sku, category, office) "
                "VALUES (1, 'Asset', 'SKU-1', 'equipment', 'Valencia')"
            ))
        migrate_programmes(self.engine)
        migrate_programmes(self.engine)
        inspector = inspect(self.engine)
        self.assertIn("unit_cost", {column["name"] for column in inspector.get_columns("asset_entries")})
        self.assertIn("locked_until", {column["name"] for column in inspector.get_columns("telemetry_outbox")})
        self.assertIn("lease_token", {column["name"] for column in inspector.get_columns("telemetry_outbox")})
        self.assertIn("ix_telemetry_outbox_claim", {index["name"] for index in inspector.get_indexes("telemetry_outbox")})
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT sku FROM assets WHERE id=1")).scalar_one(), "SKU-1")


if __name__ == "__main__":
    unittest.main()