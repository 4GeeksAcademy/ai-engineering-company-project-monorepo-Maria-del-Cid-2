"""Focused isolated tests for Phase 2 inventory event rules."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from sqlmodel import Session, SQLModel, create_engine, select

from app.inventory.migrate_programmes import migrate_phase2_events, migrate_programmes
from app.inventory.models import (
    Asset, AssetEntry, InventoryValuation, InventoryValuationLedger,
    KitConfiguration, KitPreparation, Programme, StockThreshold,
    TelemetryOutboxEvent,
)
from app.inventory.operations import (
    InventoryConflict, configure_kit, configure_stock_threshold, create_inbound,
    create_inbound, create_inventory_regularization, create_outbound,
    prepare_kit, InsufficientStock,
)
from app.inventory.schemas import (
    AssetEntryCreate, AssetExitCreate, InventoryRegularizationCreate,
    KitComponentWrite, KitConfigurationWrite, KitPreparationCreate,
    StockThresholdWrite,
)

USER = UUID("00000000-0000-0000-0000-000000000010")


class Phase2InventoryEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.tempdir.name) / 'phase2.sqlite3'}")
        SQLModel.metadata.create_all(self.engine)
        self.asset_ids: dict[str, int] = {}
        with Session(self.engine) as session:
            session.add(Programme(programme_id="prog-test", name="Test programme"))
            for sku, office in (("A", "Valencia"), ("B", "Valencia"), ("KIT", "Valencia")):
                asset = Asset(name=sku, sku=sku, category="equipment", office=office, currency="EUR")
                session.add(asset)
                session.flush()
                self.asset_ids[sku] = asset.id
            session.commit()

    def tearDown(self) -> None:
        self.engine.dispose()
        self.tempdir.cleanup()

    def inbound(self, sku: str, quantity: float, cost: float) -> None:
        with Session(self.engine) as session:
            create_inbound(session, AssetEntryCreate(
                asset_id=self.asset_ids[sku], programme_id="prog-test", quantity=quantity,
                unit_cost=cost, supplier="supplier", office="Valencia",
            ), user_uuid=USER)

    def test_threshold_emits_only_on_crossing_below_limit_and_rearms_after_restock(self) -> None:
        self.inbound("A", 5, 2)
        with Session(self.engine) as session:
            configure_stock_threshold(session, StockThresholdWrite(
                asset_id=self.asset_ids["A"], office="Valencia", threshold=3,
            ))
            create_outbound(session, AssetExitCreate(
                asset_id=self.asset_ids["A"], programme_id="prog-test", quantity=2,
                exit_type="consumption", assigned_to=None, office="Valencia",
            ), user_uuid=USER)
        with Session(self.engine) as session:
            self.assertEqual(session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "stock_threshold_triggered",
            )).all(), [])
        # Crossing from exactly 3 to 2 emits one event.
        with Session(self.engine) as session:
            create_outbound(session, AssetExitCreate(
                asset_id=self.asset_ids["A"], programme_id="prog-test", quantity=1,
                exit_type="consumption", assigned_to=None, office="Valencia",
            ), user_uuid=USER)
        with Session(self.engine) as session:
            events = session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "stock_threshold_triggered",
            )).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].tags["current_stock"], 2.0)
        with Session(self.engine) as session:
            create_outbound(session, AssetExitCreate(
                asset_id=self.asset_ids["A"], programme_id="prog-test", quantity=1,
                exit_type="consumption", assigned_to=None, office="Valencia",
            ), user_uuid=USER)
        with Session(self.engine) as session:
            # Staying below does not repeat the event; stock is 1.
            events = session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "stock_threshold_triggered",
            )).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].tags["currency"], "EUR")
            self.assertEqual(events[0].tags["current_stock"], 2.0)
            # Restock to the threshold (or above) arms the next downward crossing.
        with Session(self.engine) as session:
            create_inbound(session, AssetEntryCreate(
                asset_id=self.asset_ids["A"], programme_id="prog-test", quantity=2,
                unit_cost=2, supplier="second restock", office="Valencia",
            ), user_uuid=USER)
        with Session(self.engine) as session:
            create_outbound(session, AssetExitCreate(
                asset_id=self.asset_ids["A"], programme_id="prog-test", quantity=1,
                exit_type="consumption", assigned_to=None, office="Valencia",
            ), user_uuid=USER)
        with Session(self.engine) as session:
            events = session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "stock_threshold_triggered",
            )).all()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0].tags["currency"], "EUR")
            self.assertEqual(events[-1].tags["current_stock"], 2.0)

    def test_legacy_stock_migration_marks_unknown_and_is_rerunnable(self) -> None:
        with Session(self.engine) as session:
            session.add(AssetEntry(
                asset_id=self.asset_ids["A"], quantity=4, unit_cost=None, supplier="legacy",
                office="Valencia", currency="EUR", user_uuid=USER,
            ))
            session.commit()
        migrate_programmes(self.engine)
        migrate_phase2_events(self.engine)
        with Session(self.engine) as session:
            valuation = session.exec(select(InventoryValuation).where(
                InventoryValuation.asset_id == self.asset_ids["A"],
            )).one()
            self.assertEqual(valuation.valued_quantity, 0)
            self.assertEqual(valuation.unvalued_quantity, 4)
            valuation.unvalued_quantity = 3
            session.add(valuation)
            session.commit()
        migrate_phase2_events(self.engine)
        with Session(self.engine) as session:
            valuation = session.exec(select(InventoryValuation).where(
                InventoryValuation.asset_id == self.asset_ids["A"],
            )).one()
            self.assertEqual(valuation.unvalued_quantity, 3)

    def test_kit_preparation_snapshots_per_kit_cost_and_emits_strict_variance(self) -> None:
        self.inbound("A", 4, 6)
        self.inbound("B", 4, 6)
        with Session(self.engine) as session:
            configure_kit(session, KitConfigurationWrite(
                kit_asset_id=self.asset_ids["KIT"], office="Valencia", expected_cost=10,
                variance_threshold_percent=10,
                components=[
                    KitComponentWrite(component_asset_id=self.asset_ids["A"], quantity_per_kit=1),
                    KitComponentWrite(component_asset_id=self.asset_ids["B"], quantity_per_kit=1),
                ],
            ))
            preparation = prepare_kit(session, KitPreparationCreate(
                kit_asset_id=self.asset_ids["KIT"], office="Valencia", programme_id="prog-test", quantity=2,
                idempotency_key="test-kit-prep-1",
            ), user_uuid=USER)
            self.assertEqual(preparation.expected_cost, 10)
            self.assertEqual(preparation.actual_cost, 12)
            self.assertEqual(preparation.variance_percent, 20)
            event = session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "kit_cost_variance_detected",
            )).one()
            self.assertEqual(event.tags["preparation_id"], preparation.id)
            self.assertEqual(event.tags["actual_cost"], 12.0)
            self.assertEqual(len(preparation.composition_snapshot), 2)
            stock_after_first = session.exec(select(AssetEntry.quantity).where(
                AssetEntry.asset_id == self.asset_ids["A"],
            )).all()
            repeated = prepare_kit(session, KitPreparationCreate(
                kit_asset_id=self.asset_ids["KIT"], office="Valencia", programme_id="prog-test", quantity=2,
                idempotency_key="test-kit-prep-1",
            ), user_uuid=USER)
            self.assertEqual(repeated.id, preparation.id)
            self.assertEqual(session.exec(select(KitPreparation)).all(), [preparation])
            self.assertEqual(session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "kit_cost_variance_detected",
            )).all(), [event])
            with self.assertRaises(InventoryConflict):
                prepare_kit(session, KitPreparationCreate(
                    kit_asset_id=self.asset_ids["KIT"], office="Valencia", programme_id="prog-test", quantity=1,
                    idempotency_key="test-kit-prep-1",
                ), user_uuid=USER)

    def test_unknown_cost_prevents_variance_and_failed_kit_rolls_back(self) -> None:
        with Session(self.engine) as session:
            session.add(AssetEntry(
                asset_id=self.asset_ids["A"], quantity=1, unit_cost=None, supplier="legacy",
                office="Valencia", currency="EUR", user_uuid=USER,
            ))
            session.commit()
        migrate_programmes(self.engine)
        migrate_phase2_events(self.engine)
        self.inbound("B", 1, 7)
        with Session(self.engine) as session:
            configure_kit(session, KitConfigurationWrite(
                kit_asset_id=self.asset_ids["KIT"], office="Valencia", expected_cost=10,
                components=[
                    KitComponentWrite(component_asset_id=self.asset_ids["A"], quantity_per_kit=1),
                    KitComponentWrite(component_asset_id=self.asset_ids["B"], quantity_per_kit=1),
                ],
            ))
            result = prepare_kit(session, KitPreparationCreate(
                kit_asset_id=self.asset_ids["KIT"], office="Valencia", programme_id="prog-test", quantity=1,
            ), user_uuid=USER)
            self.assertTrue(result.incomplete_cost)
            self.assertIsNone(result.actual_cost)
            self.assertEqual(session.exec(select(TelemetryOutboxEvent).where(
                TelemetryOutboxEvent.event_type == "kit_cost_variance_detected",
            )).all(), [])
        with Session(self.engine) as session:
            before = session.exec(select(InventoryValuationLedger)).all()
        with Session(self.engine) as session:
            with self.assertRaises(InsufficientStock):
                prepare_kit(session, KitPreparationCreate(
                    kit_asset_id=self.asset_ids["KIT"], office="Valencia", programme_id="prog-test", quantity=5,
                ), user_uuid=USER)
        with Session(self.engine) as session:
            after = session.exec(select(InventoryValuationLedger)).all()
            self.assertEqual(len(before), len(after))

    def test_regularization_is_explicit_and_audited(self) -> None:
        with Session(self.engine) as session:
            session.add(AssetEntry(
                asset_id=self.asset_ids["A"], quantity=3, unit_cost=None, supplier="legacy",
                office="Valencia", currency="EUR", user_uuid=USER,
            ))
            session.commit()
        migrate_programmes(self.engine)
        migrate_phase2_events(self.engine)
        with Session(self.engine) as session:
            row = create_inventory_regularization(session, InventoryRegularizationCreate(
                asset_id=self.asset_ids["A"], office="Valencia", quantity=2,
                approved_unit_cost=9, reason="Invoice verified",
            ), user_uuid=USER)
            self.assertEqual(row.approved_unit_cost, 9)
            valuation = session.exec(select(InventoryValuation).where(
                InventoryValuation.asset_id == self.asset_ids["A"],
            )).one()
            self.assertEqual(valuation.valued_quantity, 2)
            self.assertEqual(valuation.unvalued_quantity, 1)


if __name__ == "__main__":
    unittest.main()
