"""Explicit, guarded development seed for inventory demo data.

Run from ``services/api`` with ``uv run python -m app.inventory.seed`` only
against an explicitly named development/test database. This module is never
imported by application startup.
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlmodel import Session
from tinydb import Query, TinyDB
from tinydb.storages import JSONStorage

from app.auth.database import get_database_path
from .database import get_engine
from .models import Asset, AssetEntry, AssetExit, KitPreparation, Programme, StockThreshold
from .operations import configure_kit, configure_stock_threshold, currency_for_office, create_inbound, create_outbound, prepare_kit
from .schemas import (
    AssetEntryCreate, AssetExitCreate, KitComponentWrite, KitConfigurationWrite,
    KitPreparationCreate, StockThresholdWrite,
)

SEED_USER_EMAIL_VARIABLE = "NEXOVA_INVENTORY_SEED_USER_EMAIL"
SEED_ENVIRONMENT_ARGUMENT = "--environment"
DATABASE_URL_VARIABLE = "DATABASE_URL"
_ALLOWED_ENVIRONMENTS = {"development", "test"}
_AUTHORIZED_SUPABASE_PROJECT_REF = "yamhkvudzwcqsbqvfmox"
_DEMO_PROGRAMME_IDS = (
    "prog-digital-skills-001",
    "prog-technical-onboarding-001",
    "prog-professional-development-001",
)
# A transaction-scoped PostgreSQL lock serializes concurrent runs of this seed.
_POSTGRES_ADVISORY_LOCK_KEY = 5_842_914_773_201_105_007

HISTORICAL_ASSET_SEED: tuple[dict[str, str], ...] = (
    {
        "name": 'Portátil 14" Business',
        "sku": "NXV-IT-001",
        "category": "hardware",
        "office": "Valencia",
    },
    {
        "name": 'Portátil 14" Business',
        "sku": "NXV-IT-002",
        "category": "hardware",
        "office": "Miami",
    },
    {
        "name": "Ratón ergonómico",
        "sku": "NXV-PER-001",
        "category": "peripherals",
        "office": "Valencia",
    },
    {
        "name": "Hub USB-C",
        "sku": "NXV-PER-002",
        "category": "peripherals",
        "office": "Miami",
    },
    {
        "name": "Resma de papel A4",
        "sku": "NXV-OFF-001",
        "category": "office_supplies",
        "office": "Valencia",
    },
    {
        "name": "Cuaderno de formación en liderazgo",
        "sku": "NXV-TRN-001",
        "category": "training_materials",
        "office": "Valencia",
    },
)

HISTORICAL_ENTRY_SEED: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-IT-001", "quantity": 10.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-IT-001", "quantity": 5.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-PER-001", "quantity": 8.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-PER-002", "quantity": 12.0, "supplier": "Office Depot Miami", "office": "Miami"},
)

HISTORICAL_EXIT_SEED: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-IT-001", "quantity": 2.0, "exit_type": "allocation", "assigned_to": "María García", "office": "Valencia"},
    {"sku": "NXV-IT-001", "quantity": 1.0, "exit_type": "consumption", "assigned_to": None, "office": "Valencia"},
    {"sku": "NXV-PER-001", "quantity": 1.0, "exit_type": "allocation", "assigned_to": "Carlos López", "office": "Valencia"},
)

# Backwards-compatible names for the original protected seed's public test surface.
ASSET_SEED = HISTORICAL_ASSET_SEED
ENTRY_SEED = HISTORICAL_ENTRY_SEED
EXIT_SEED = HISTORICAL_EXIT_SEED

_DEMO_PRODUCTS: tuple[tuple[str, str, str], ...] = (
    ("Training Manual", "training_materials", "NXV-DEMO-MANUAL"),
    ("Training Workbook", "training_materials", "NXV-DEMO-WORKBOOK"),
    ("Learning Materials", "training_kit", "NXV-DEMO-LEARNING-KIT"),
    ("Certification Voucher", "certification", "NXV-DEMO-VOUCHER"),
    ("Exam Preparation Pack", "certification", "NXV-DEMO-EXAM-PACK"),
    ("Laptop", "onboarding_equipment", "NXV-DEMO-LAPTOP"),
    ("Headset", "peripherals", "NXV-DEMO-HEADSET"),
    ("Wireless Mouse", "peripherals", "NXV-DEMO-MOUSE"),
)

# Product variants are explicitly separate assets because office, stock, and
# currency are asset-level dimensions in the current inventory model.
DEMO_ASSET_SEED: tuple[dict[str, str], ...] = tuple(
    {
        "name": name,
        "sku": f"{sku}-{office_code}",
        "category": category,
        "office": office,
    }
    for name, category, sku in _DEMO_PRODUCTS
    for office_code, office in (("VAL", "Valencia"), ("MIA", "Miami"))
)

# Demo inbound unit costs (EUR for Valencia, USD for Miami) come from the
# business-approved test matrix, never from event payload construction.
_DEMO_UNIT_COSTS: dict[tuple[str, str], float] = {
    ("Training Manual", "Valencia"): 6,
    ("Training Manual", "Miami"): 8,
    ("Training Workbook", "Valencia"): 8,
    ("Training Workbook", "Miami"): 10,
    ("Learning Materials", "Valencia"): 12,
    ("Learning Materials", "Miami"): 15,
    ("Certification Voucher", "Valencia"): 10,
    ("Certification Voucher", "Miami"): 12,
    ("Exam Preparation Pack", "Valencia"): 75,
    ("Exam Preparation Pack", "Miami"): 90,
    ("Laptop", "Valencia"): 500,
    ("Laptop", "Miami"): 750,
    ("Headset", "Valencia"): 25,
    ("Headset", "Miami"): 35,
    ("Wireless Mouse", "Valencia"): 20,
    ("Wireless Mouse", "Miami"): 30,
}

_DEMO_ENTRIES: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-DEMO-MANUAL-VAL", "quantity": 6.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-WORKBOOK-MIA", "quantity": 6.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-WORKBOOK-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-HEADSET-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-LEARNING-KIT-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-LEARNING-KIT-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-VOUCHER-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-VOUCHER-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-EXAM-PACK-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-EXAM-PACK-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-LAPTOP-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-HEADSET-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[1]},
)
_DEMO_ENTRIES = tuple(
    {
        **movement,
        "supplier": f"Demo Supplier {movement['office']}",
        "unit_cost": _DEMO_UNIT_COSTS[(
            next(name for name, _category, base in _DEMO_PRODUCTS
                 if movement["sku"].startswith(base)), movement["office"]
        )],
        "seed_key": f"inventory-demo:entry:{movement['sku']}:primary",
    }
    for movement in _DEMO_ENTRIES
)

# The two threshold scenarios start at 5/6 units and finish at 2. Other
# exits are distributed across both offices and all approved programmes.
_DEMO_EXITS: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-DEMO-MANUAL-VAL", "quantity": 3.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-WORKBOOK-MIA", "quantity": 4.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-LEARNING-KIT-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-LEARNING-KIT-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-VOUCHER-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-VOUCHER-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-EXAM-PACK-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[1]},
    {"sku": "NXV-DEMO-EXAM-PACK-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[2]},
    {"sku": "NXV-DEMO-LAPTOP-VAL", "quantity": 1.0, "office": "Valencia", "programme_id": _DEMO_PROGRAMME_IDS[0]},
    {"sku": "NXV-DEMO-HEADSET-MIA", "quantity": 1.0, "office": "Miami", "programme_id": _DEMO_PROGRAMME_IDS[1]},
)


class SeedSafetyError(RuntimeError):
    """Raised when the configured target or existing rows are unsafe to seed."""


def _supabase_project_ref(url: Any) -> str | None:
    """Extract a Supabase project ref without exposing URL components."""

    host = (url.host or "").lower()
    if host.endswith(".pooler.supabase.com"):
        username = url.username or ""
        if username.startswith("postgres."):
            return username.removeprefix("postgres.")
        return None

    if host.endswith(".supabase.co"):
        labels = host.removesuffix(".supabase.co").split(".")
        if len(labels) == 2 and labels[0] == "db":
            return labels[1]
    return None


def validate_seed_target(environment: str, database_url: str) -> None:
    """Require an explicit matching environment marker and database identity.

    URL values are deliberately never included in errors or output. PostgreSQL
    databases must end in ``_dev`` or ``_test`` unless development targets the
    explicitly authorized Supabase project, whose standard database is named
    ``postgres``. Supabase targets are never accepted for the test environment.
    SQLite files must use the corresponding ``_dev.sqlite3``/``_test.sqlite3``
    (or ``.db``) suffix. In-memory SQLite is accepted only for tests.
    """

    normalized_environment = environment.strip().lower()
    if normalized_environment not in _ALLOWED_ENVIRONMENTS:
        raise SeedSafetyError(
            f"{SEED_ENVIRONMENT_ARGUMENT} must explicitly be 'development' or 'test'."
        )
    if not database_url.strip():
        raise SeedSafetyError(f"{DATABASE_URL_VARIABLE} is required.")

    try:
        url = make_url(database_url)
    except Exception as exc:
        raise SeedSafetyError("The configured inventory database target is invalid.") from exc

    expected_suffix = "_dev" if normalized_environment == "development" else "_test"
    backend = url.get_backend_name()
    if backend == "postgresql":
        database_name = url.database or ""
        host = (url.host or "").lower()
        is_supabase = host.endswith((".supabase.co", ".pooler.supabase.com"))
        if is_supabase:
            project_ref = _supabase_project_ref(url)
            safe_database_name = (
                normalized_environment == "development"
                and project_ref == _AUTHORIZED_SUPABASE_PROJECT_REF
                and (database_name == "postgres" or database_name.endswith("_dev"))
            )
        else:
            safe_database_name = database_name.endswith(expected_suffix)
    elif backend == "sqlite":
        database_name = url.database or ""
        if database_name == ":memory:":
            safe_database_name = normalized_environment == "test"
        else:
            lower_name = database_name.lower()
            safe_database_name = lower_name.endswith(
                (f"{expected_suffix}.sqlite3", f"{expected_suffix}.db")
            )
    else:
        safe_database_name = False

    if not safe_database_name:
        raise SeedSafetyError(
            "The database identity does not explicitly match the selected "
            "development/test environment; no data was changed."
        )


def resolve_seed_user_uuid(email: str) -> UUID:
    """Resolve one active user from the configured local auth TinyDB, read-only.

    The caller supplies the authorized development account's email locally.
    No user data or UUID is emitted, and old records without a persisted UUID
    are rejected rather than assigned a newly generated identity.
    """

    normalized_email = email.strip().casefold()
    if not normalized_email:
        raise SeedSafetyError(f"{SEED_USER_EMAIL_VARIABLE} is required.")

    database_path = get_database_path()
    if not database_path.is_file():
        raise SeedSafetyError("The configured local auth database is unavailable.")

    try:
        with TinyDB(database_path, storage=JSONStorage, access_mode="r") as database:
            records = database.table("users").search(
                Query().email.test(
                    lambda value: isinstance(value, str)
                    and value.strip().casefold() == normalized_email
                )
            )
    except Exception as exc:
        raise SeedSafetyError("The configured local auth database could not be read safely.") from exc

    if len(records) != 1:
        raise SeedSafetyError("The authorized development account was not uniquely identified.")

    record = records[0]
    if record.get("is_active", True) is not True:
        raise SeedSafetyError("The authorized development account is not active.")

    try:
        user_uuid = UUID(str(record.get("user_uuid", "")))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SeedSafetyError(
            "The authorized development account has no valid persisted user UUID."
        ) from exc
    return user_uuid


def _acquire_seed_lock(session: Session) -> None:
    """Serialize this seed on PostgreSQL; SQLite is used only for isolated tests."""

    if session.get_bind().dialect.name == "postgresql":
        session.connection(execution_options={"isolation_level": "READ COMMITTED"})
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _POSTGRES_ADVISORY_LOCK_KEY},
        )


def _existing_or_insert_asset(
    session: Session,
    payload: dict[str, str],
) -> tuple[Asset, bool]:
    result = session.exec(select(Asset).where(Asset.sku == payload["sku"])).first()
    asset = result[0] if result is not None else None
    if asset is not None:
        actual = {key: getattr(asset, key) for key in payload}
        if actual != payload:
            raise SeedSafetyError(
                f"SKU {payload['sku']} already exists with different asset data; "
                "no existing row was changed."
            )
        return asset, False

    asset = Asset(**payload, currency=currency_for_office(payload["office"]))
    session.add(asset)
    session.flush()
    return asset, True


def _entry_exists(session: Session, values: dict[str, Any]) -> bool:
    statement = select(AssetEntry.id).where(
        AssetEntry.asset_id == values["asset_id"],
        AssetEntry.quantity == values["quantity"],
        AssetEntry.supplier == values["supplier"],
        AssetEntry.office == values["office"],
        AssetEntry.programme_id == values["programme_id"],
        AssetEntry.user_uuid == values["user_uuid"],
    )
    return session.exec(statement).first() is not None


def _exit_exists(session: Session, values: dict[str, Any]) -> bool:
    statement = select(AssetExit.id).where(
        AssetExit.asset_id == values["asset_id"],
        AssetExit.quantity == values["quantity"],
        AssetExit.exit_type == values["exit_type"],
        AssetExit.assigned_to == values["assigned_to"],
        AssetExit.office == values["office"],
        AssetExit.programme_id == values["programme_id"],
        AssetExit.user_uuid == values["user_uuid"],
    )
    return session.exec(statement).first() is not None


def _demo_movement_exists(
    session: Session,
    movement_type: str,
    seed_key: str,
    expected: dict[str, Any],
    assets_by_sku: dict[str, Asset],
    user_uuid: UUID,
) -> bool:
    model = AssetEntry if movement_type == "entry" else AssetExit
    existing = session.scalars(select(model).where(model.seed_key == seed_key)).first()
    if existing is None:
        return False

    comparable_fields = (
        ("quantity", "supplier", "office", "programme_id", "unit_cost", "user_uuid")
        if movement_type == "entry"
        else ("quantity", "exit_type", "assigned_to", "office", "programme_id", "user_uuid")
    )
    expected_values = {
        "asset_id": assets_by_sku[expected["sku"]].id,
        "quantity": expected["quantity"],
        "office": expected["office"],
        "programme_id": expected["programme_id"],
        "user_uuid": user_uuid,
    }
    if movement_type == "entry":
        expected_values.update({"supplier": expected["supplier"], "unit_cost": expected["unit_cost"]})
    else:
        expected_values.update({"exit_type": "consumption", "assigned_to": None})

    def normalized(value: Any) -> Any:
        return Decimal(str(value)) if isinstance(value, (int, float, Decimal)) else value

    if existing.asset_id != expected_values["asset_id"] or any(
        normalized(getattr(existing, field)) != normalized(expected_values[field])
        for field in comparable_fields
    ):
        raise SeedSafetyError(
            f"Demo movement key {seed_key} exists with a different payload; no row was changed."
        )
    return True


def _current_stock(session: Session, asset_id: int) -> float:
    entries = session.exec(
        select(func.coalesce(func.sum(AssetEntry.quantity), 0.0)).where(
            AssetEntry.asset_id == asset_id
        )
    ).one()
    exits = session.exec(
        select(func.coalesce(func.sum(AssetExit.quantity), 0.0)).where(
            AssetExit.asset_id == asset_id
        )
    ).one()
    return float(entries[0]) - float(exits[0])


def seed_inventory(session: Session, user_uuid: UUID, programme_id: str) -> dict[str, int]:
    """Insert missing demo rows in one transaction without updating/deleting rows.

    Movement identity is the exact tuple of domain fields plus the supplied
    user UUID (timestamps and generated primary keys are excluded). A natural
    existing movement with the same tuple is treated as already seeded.
    """

    if session.in_transaction():
        raise SeedSafetyError(
            "Seed requires a clean session with no open transaction; no data was changed."
        )

    inserted = {"assets": 0, "entries": 0, "exits": 0}
    try:
        with session.begin():
            _acquire_seed_lock(session)
            if session.get(Programme, programme_id) is None:
                raise SeedSafetyError("The selected programme does not exist; no data was changed.")
            assets_by_sku: dict[str, Asset] = {}
            for payload in HISTORICAL_ASSET_SEED:
                asset, was_inserted = _existing_or_insert_asset(session, payload)
                assets_by_sku[payload["sku"]] = asset
                inserted["assets"] += int(was_inserted)

            session.flush()
            available_by_asset = {
                asset.id: _current_stock(session, asset.id)
                for asset in assets_by_sku.values()
                if asset.id is not None
            }
            if any(stock < 0 for stock in available_by_asset.values()):
                raise SeedSafetyError(
                    "An existing asset has negative derived stock; no data was changed."
                )

            for seed_entry in HISTORICAL_ENTRY_SEED:
                asset_id = assets_by_sku[seed_entry["sku"]].id
                if asset_id is None:
                    raise SeedSafetyError("An asset ID was not assigned; no data was changed.")
                values = {
                    "asset_id": asset_id,
                    "quantity": seed_entry["quantity"],
                    "supplier": seed_entry["supplier"],
                    "office": seed_entry["office"],
                    "currency": currency_for_office(seed_entry["office"]),
                    "programme_id": programme_id,
                    "user_uuid": user_uuid,
                }
                if _entry_exists(session, values):
                    continue
                session.add(AssetEntry(**values))
                inserted["entries"] += 1

            session.flush()
            # Include existing and newly inserted inbound movements before
            # checking the outbound seed against available stock.
            available_by_asset = {
                asset_id: _current_stock(session, asset_id)
                for asset_id in available_by_asset
            }

            for seed_exit in HISTORICAL_EXIT_SEED:
                asset_id = assets_by_sku[seed_exit["sku"]].id
                if asset_id is None:
                    raise SeedSafetyError("An asset ID was not assigned; no data was changed.")
                values = {
                    "asset_id": asset_id,
                    "quantity": seed_exit["quantity"],
                    "exit_type": seed_exit["exit_type"],
                    "assigned_to": seed_exit["assigned_to"],
                    "office": seed_exit["office"],
                    "currency": currency_for_office(seed_exit["office"]),
                    "programme_id": programme_id,
                    "user_uuid": user_uuid,
                }
                if _exit_exists(session, values):
                    continue
                available = available_by_asset[asset_id]
                if seed_exit["quantity"] > available:
                    raise SeedSafetyError(
                        f"Seed exit for SKU {seed_exit['sku']} would make stock negative; "
                        "no data was changed."
                    )
                session.add(AssetExit(**values))
                available_by_asset[asset_id] = available - seed_exit["quantity"]
                inserted["exits"] += 1

        return inserted
    except Exception:
        session.rollback()
        raise


def seed_demo_inventory(session: Session, user_uuid: UUID) -> dict[str, int]:
    """Seed the approved demo scenario through domain operations and outbox.

    The whole fixture runs in one transaction, and stable seed keys make it
    safe to rerun without duplicating movements, preparations, or events.
    """
    if session.in_transaction():
        raise SeedSafetyError("Demo seed requires a clean session; no data was changed.")

    counts = {"assets": 0, "entries": 0, "exits": 0, "thresholds": 0, "kit_preparations": 0}
    try:
        with session.begin():
            _acquire_seed_lock(session)
            programmes = {row.programme_id for row in session.scalars(select(Programme)).all()}
            if not set(_DEMO_PROGRAMME_IDS).issubset(programmes):
                raise SeedSafetyError("All three approved programmes must already exist.")

            assets_by_sku: dict[str, Asset] = {}
            for payload in DEMO_ASSET_SEED:
                asset, created = _existing_or_insert_asset(session, payload)
                assets_by_sku[payload["sku"]] = asset
                counts["assets"] += int(created)
            session.flush()

            # Baseline inventory is deliberately appended (not reconstructed or
            # overwritten); seed_key protects retries while domain operations
            # create valuation, ledger, and transactional outbox rows.
            for movement in _DEMO_ENTRIES:
                if _demo_movement_exists(
                    session, "entry", movement["seed_key"], movement, assets_by_sku, user_uuid,
                ):
                    continue
                asset = assets_by_sku[movement["sku"]]
                create_inbound(session, AssetEntryCreate(
                    asset_id=asset.id, programme_id=movement["programme_id"],
                    quantity=movement["quantity"], unit_cost=movement["unit_cost"],
                    supplier=movement["supplier"], office=movement["office"],
                    seed_key=movement["seed_key"],
                ), user_uuid=user_uuid)
                counts["entries"] += 1

            for sku, office in (("NXV-DEMO-MANUAL-VAL", "Valencia"), ("NXV-DEMO-WORKBOOK-MIA", "Miami")):
                asset = assets_by_sku[sku]
                existing = session.scalars(select(StockThreshold).where(
                    StockThreshold.asset_id == asset.id, StockThreshold.office == office,
                )).first()
                if existing is not None and existing.threshold != 3:
                    raise SeedSafetyError(f"Demo threshold for {sku} already has a conflicting value.")
                if existing is None:
                    configure_stock_threshold(session, StockThresholdWrite(
                        asset_id=asset.id, office=office, threshold=3,
                    ))
                    counts["thresholds"] += 1

            # All ordinary exits run before kit preparation so its three
            # component consumptions remain distinct and count as outbound.
            for index, movement in enumerate(_DEMO_EXITS):
                seed_key = f"inventory-demo:exit:{movement['sku']}:scenario"
                if _demo_movement_exists(
                    session, "exit", seed_key, {**movement, "seed_key": seed_key}, assets_by_sku, user_uuid,
                ):
                    continue
                asset = assets_by_sku[movement["sku"]]
                create_outbound(session, AssetExitCreate(
                    asset_id=asset.id, programme_id=movement["programme_id"],
                    quantity=movement["quantity"], exit_type="consumption",
                    assigned_to=None, office=movement["office"], seed_key=seed_key,
                ), user_uuid=user_uuid)
                counts["exits"] += 1

            kit = assets_by_sku["NXV-DEMO-LEARNING-KIT-VAL"]
            manual = assets_by_sku["NXV-DEMO-MANUAL-VAL"]
            workbook = assets_by_sku["NXV-DEMO-WORKBOOK-VAL"]
            headset = assets_by_sku["NXV-DEMO-HEADSET-VAL"]
            configure_kit(session, KitConfigurationWrite(
                kit_asset_id=kit.id, office="Valencia", expected_cost=20,
                variance_threshold_percent=10,
                components=[
                    KitComponentWrite(component_asset_id=manual.id, quantity_per_kit=1),
                    KitComponentWrite(component_asset_id=workbook.id, quantity_per_kit=1),
                    KitComponentWrite(component_asset_id=headset.id, quantity_per_kit=1),
                ],
            ))
            prep_key = "inventory-demo:kit:training-starter-kit:valencia:v1"
            prep_before = session.scalars(select(KitPreparation).where(
                KitPreparation.idempotency_key == prep_key,
            )).first()
            if prep_before is None:
                prepare_kit(session, KitPreparationCreate(
                    kit_asset_id=kit.id, office="Valencia",
                    programme_id=_DEMO_PROGRAMME_IDS[2], quantity=1,
                    idempotency_key=prep_key,
                ), user_uuid=user_uuid)
                counts["kit_preparations"] = 1

        counts["exits_total"] = counts["exits"] + counts["kit_preparations"] * 3
        return counts
    except Exception:
        session.rollback()
        raise


def main(environment: str, programme_id: str | None = None, *, demo: bool = False) -> int:
    """Run only when the CLI caller explicitly selects a safe environment."""

    database_url = os.environ.get(DATABASE_URL_VARIABLE, "")
    raw_user_email = os.environ.get(SEED_USER_EMAIL_VARIABLE, "")
    try:
        validate_seed_target(environment, database_url)
        if not demo and not programme_id:
            raise SeedSafetyError("--programme-id is required to seed new movements.")
        user_uuid = resolve_seed_user_uuid(raw_user_email)

        # Target checks happen before asking the lazy inventory boundary for an engine.
        engine = get_engine()
        with Session(engine) as session:
            counts = seed_demo_inventory(session, user_uuid) if demo else seed_inventory(session, user_uuid, programme_id)
        print(
            "Inventory seed completed: "
            f"{counts['assets']} assets, {counts['entries']} entries, "
            f"{counts['exits']} exits inserted."
        )
        return 0
    except (SeedSafetyError, ValueError) as exc:
        # Messages are controlled, and no URL, credential, or user data is printed.
        print(f"Inventory seed refused or failed: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("Inventory seed failed; no partial transaction was committed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Nexova inventory demo data safely.")
    parser.add_argument(
        "--environment",
        required=True,
        choices=sorted(_ALLOWED_ENVIRONMENTS),
        help="Explicit target environment; this opt-in is not read from dotenv.",
    )
    parser.add_argument("--programme-id", help="Existing programme for historical-style demo movements.")
    parser.add_argument(
        "--demo", action="store_true",
        help="Seed the approved two-office fixture and business events (requires all three approved programmes).",
    )
    args = parser.parse_args()
    raise SystemExit(main(args.environment, args.programme_id, demo=args.demo))
