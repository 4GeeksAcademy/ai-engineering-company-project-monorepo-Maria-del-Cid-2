"""Transactional inventory writes and their domain-level validation."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from .models import Asset, AssetEntry, AssetExit
from .schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryResponse,
    AssetExitCreate,
    AssetExitResponse,
    AssetWithStockResponse,
)


def create_asset(session: Session, payload: AssetCreate) -> AssetWithStockResponse:
    """Create a product; a new product has derived stock zero."""

    asset = Asset(**payload.model_dump())
    try:
        with session.begin():
            session.add(asset)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise InventoryConflict("A product with this SKU already exists.") from exc

    session.refresh(asset)
    return AssetWithStockResponse.model_validate(
        {**asset.model_dump(), "current_stock": 0.0}
    )


def create_inbound(
    session: Session,
    payload: AssetEntryCreate,
    *,
    user_uuid: UUID,
) -> AssetEntryResponse:
    """Record one inbound movement atomically."""

    movement = AssetEntry(**payload.model_dump(), user_uuid=user_uuid)
    try:
        with session.begin():
            _require_asset(session, payload.asset_id)
            session.add(movement)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise InventoryConflict("The inventory movement conflicts with stored data.") from exc

    session.refresh(movement)
    return AssetEntryResponse.model_validate(movement)


def create_outbound(
    session: Session,
    payload: AssetExitCreate,
    *,
    user_uuid: UUID,
) -> AssetExitResponse:
    """Record an outbound movement without permitting negative stock.

    PostgreSQL serializes competing exits by locking the owning asset row with
    ``SELECT ... FOR UPDATE``. The lock is held through commit. The stock query
    runs after acquiring the lock, so under READ COMMITTED it observes the
    previous lock holder's committed exit before deciding whether this exit is
    affordable. SQLite ignores this row lock and is not a concurrency proof.
    """

    movement = AssetExit(**payload.model_dump(), user_uuid=user_uuid)
    try:
        with session.begin():
            _set_postgres_read_committed(session)
            _require_asset(session, payload.asset_id, lock_for_update=True)
            available_stock = _stock_for_asset(session, payload.asset_id)
            if payload.quantity > available_stock:
                raise InsufficientStock("Insufficient stock for this outbound movement.")

            session.add(movement)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise InventoryConflict("The inventory movement conflicts with stored data.") from exc

    session.refresh(movement)
    return AssetExitResponse.model_validate(movement)


class InventoryConflict(Exception):
    """A database uniqueness or integrity conflict in an inventory write."""


class InsufficientStock(Exception):
    """An outbound movement exceeds the derived stock available."""


def _require_asset(
    session: Session,
    asset_id: int,
    *,
    lock_for_update: bool = False,
) -> Asset:
    statement = _asset_lookup_statement(
        asset_id,
        lock_for_update=(
            lock_for_update and session.get_bind().dialect.name == "postgresql"
        ),
    )

    asset = session.exec(statement).first()
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found.",
        )
    return asset


def _asset_lookup_statement(asset_id: int, *, lock_for_update: bool):
    statement = select(Asset).where(Asset.id == asset_id)
    return statement.with_for_update() if lock_for_update else statement


def _set_postgres_read_committed(session: Session) -> None:
    """Use per-statement snapshots for correct post-lock aggregates in PostgreSQL."""

    if session.get_bind().dialect.name == "postgresql":
        session.connection(execution_options={"isolation_level": "READ COMMITTED"})


def _stock_for_asset(session: Session, asset_id: int) -> float:
    entries = session.exec(
        select(func.coalesce(func.sum(AssetEntry.quantity), 0.0)).where(
            AssetEntry.asset_id == asset_id
        )
    ).one()[0]
    exits = session.exec(
        select(func.coalesce(func.sum(AssetExit.quantity), 0.0)).where(
            AssetExit.asset_id == asset_id
        )
    ).one()[0]
    return float(entries) - float(exits)