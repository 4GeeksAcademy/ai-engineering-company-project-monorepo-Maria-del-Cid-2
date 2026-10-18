"""Explicit, guarded development seed for inventory demo data.

Run from ``services/api`` with ``uv run python -m app.inventory.seed`` only
against an explicitly named development/test database. This module is never
imported by application startup.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlmodel import Session

from .database import get_engine
from .models import Asset, AssetEntry, AssetExit

SEED_ENVIRONMENT_VARIABLE = "NEXOVA_INVENTORY_SEED_ENV"
SEED_USER_UUID_VARIABLE = "NEXOVA_INVENTORY_SEED_USER_UUID"
DATABASE_URL_VARIABLE = "DATABASE_URL"
_ALLOWED_ENVIRONMENTS = {"development", "test"}
# A transaction-scoped PostgreSQL lock serializes concurrent runs of this seed.
_POSTGRES_ADVISORY_LOCK_KEY = 5_842_914_773_201_105_007

ASSET_SEED: tuple[dict[str, str], ...] = (
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

ENTRY_SEED: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-IT-001", "quantity": 10.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-IT-001", "quantity": 5.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-PER-001", "quantity": 8.0, "supplier": "TechDistrib Valencia S.L.", "office": "Valencia"},
    {"sku": "NXV-IT-002", "quantity": 10.0, "supplier": "Office Depot Miami", "office": "Miami"},
)

EXIT_SEED: tuple[dict[str, Any], ...] = (
    {"sku": "NXV-IT-001", "quantity": 3.0, "exit_type": "allocation", "assigned_to": "Alex Morgan", "office": "Valencia"},
    {"sku": "NXV-IT-001", "quantity": 2.0, "exit_type": "consumption", "assigned_to": None, "office": "Valencia"},
    {"sku": "NXV-PER-001", "quantity": 1.0, "exit_type": "allocation", "assigned_to": "Jamie Lee", "office": "Valencia"},
)


class SeedSafetyError(RuntimeError):
    """Raised when the configured target or existing rows are unsafe to seed."""


def validate_seed_target(environment: str, database_url: str) -> None:
    """Require an explicit matching environment marker and database identity.

    URL values are deliberately never included in errors or output. PostgreSQL
    databases must end in ``_dev`` or ``_test``; SQLite files must use the
    corresponding ``_dev.sqlite3``/``_test.sqlite3`` (or ``.db``) suffix.
    In-memory SQLite is accepted only for the test environment.
    """

    normalized_environment = environment.strip().lower()
    if normalized_environment not in _ALLOWED_ENVIRONMENTS:
        raise SeedSafetyError(
            f"{SEED_ENVIRONMENT_VARIABLE} must explicitly be 'development' or 'test'."
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

    asset = Asset(**payload)
    session.add(asset)
    session.flush()
    return asset, True


def _entry_exists(session: Session, values: dict[str, Any]) -> bool:
    statement = select(AssetEntry.id).where(
        AssetEntry.asset_id == values["asset_id"],
        AssetEntry.quantity == values["quantity"],
        AssetEntry.supplier == values["supplier"],
        AssetEntry.office == values["office"],
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
        AssetExit.user_uuid == values["user_uuid"],
    )
    return session.exec(statement).first() is not None


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


def seed_inventory(session: Session, user_uuid: UUID) -> dict[str, int]:
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
            assets_by_sku: dict[str, Asset] = {}
            for payload in ASSET_SEED:
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

            for seed_entry in ENTRY_SEED:
                asset_id = assets_by_sku[seed_entry["sku"]].id
                if asset_id is None:
                    raise SeedSafetyError("An asset ID was not assigned; no data was changed.")
                values = {
                    "asset_id": asset_id,
                    "quantity": seed_entry["quantity"],
                    "supplier": seed_entry["supplier"],
                    "office": seed_entry["office"],
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

            for seed_exit in EXIT_SEED:
                asset_id = assets_by_sku[seed_exit["sku"]].id
                if asset_id is None:
                    raise SeedSafetyError("An asset ID was not assigned; no data was changed.")
                values = {
                    "asset_id": asset_id,
                    "quantity": seed_exit["quantity"],
                    "exit_type": seed_exit["exit_type"],
                    "assigned_to": seed_exit["assigned_to"],
                    "office": seed_exit["office"],
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


def main() -> int:
    """Run the seed only after validating both explicit environment fences."""

    environment = os.environ.get(SEED_ENVIRONMENT_VARIABLE, "")
    database_url = os.environ.get(DATABASE_URL_VARIABLE, "")
    raw_user_uuid = os.environ.get(SEED_USER_UUID_VARIABLE, "")
    try:
        validate_seed_target(environment, database_url)
        if not raw_user_uuid.strip():
            raise SeedSafetyError(
                f"{SEED_USER_UUID_VARIABLE} must be set to an existing development user's UUID."
            )
        user_uuid = UUID(raw_user_uuid.strip())

        # Target checks happen before asking the lazy inventory boundary for an engine.
        engine = get_engine()
        with Session(engine) as session:
            counts = seed_inventory(session, user_uuid)
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
    raise SystemExit(main())
