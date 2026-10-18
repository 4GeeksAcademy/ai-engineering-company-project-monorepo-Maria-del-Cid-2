"""Read queries for inventory assets and movement records."""

from __future__ import annotations

from sqlalchemy import func, literal, select, union_all
from sqlmodel import Session

from .models import Asset, AssetEntry, AssetExit


def list_assets_with_stock(session: Session) -> list[tuple[Asset, float]]:
    """Return assets and stock calculated from pre-aggregated movement sums.

    Entries and exits are aggregated independently before they are joined to
    assets, preventing a many-to-many multiplication of movement rows.
    """

    entry_totals = (
        select(
            AssetEntry.asset_id.label("asset_id"),
            func.sum(AssetEntry.quantity).label("total"),
        )
        .group_by(AssetEntry.asset_id)
        .subquery("entry_totals")
    )
    exit_totals = (
        select(
            AssetExit.asset_id.label("asset_id"),
            func.sum(AssetExit.quantity).label("total"),
        )
        .group_by(AssetExit.asset_id)
        .subquery("exit_totals")
    )
    statement = (
        select(
            Asset,
            (
                func.coalesce(entry_totals.c.total, 0.0)
                - func.coalesce(exit_totals.c.total, 0.0)
            ).label("current_stock"),
        )
        .outerjoin(entry_totals, entry_totals.c.asset_id == Asset.id)
        .outerjoin(exit_totals, exit_totals.c.asset_id == Asset.id)
        .order_by(Asset.id)
    )
    return [(asset, float(stock)) for asset, stock in session.exec(statement).all()]


def get_asset_with_stock(session: Session, asset_id: int) -> tuple[Asset, float] | None:
    """Return one asset with its derived stock, or None when it does not exist."""

    entry_total = (
        select(func.sum(AssetEntry.quantity))
        .where(AssetEntry.asset_id == Asset.id)
        .correlate(Asset)
        .scalar_subquery()
    )
    exit_total = (
        select(func.sum(AssetExit.quantity))
        .where(AssetExit.asset_id == Asset.id)
        .correlate(Asset)
        .scalar_subquery()
    )
    statement = select(
        Asset,
        (func.coalesce(entry_total, 0.0) - func.coalesce(exit_total, 0.0)).label(
            "current_stock"
        ),
    ).where(Asset.id == asset_id)
    result = session.exec(statement).first()
    if result is None:
        return None
    asset, stock = result
    return asset, float(stock)


def list_inventory_orders(session: Session) -> list[dict[str, object]]:
    """Return entries and exits in one stable, newest-first movement list."""

    entry_rows = select(
        AssetEntry.id.label("id"),
        AssetEntry.asset_id.label("asset_id"),
        AssetEntry.quantity.label("quantity"),
        literal("entry").label("type"),
        AssetEntry.supplier.label("supplier"),
        AssetEntry.office.label("office"),
        AssetEntry.created_at.label("created_at"),
        AssetEntry.user_uuid.label("user_uuid"),
        literal(None).label("exit_type"),
        literal(None).label("assigned_to"),
    )
    exit_rows = select(
        AssetExit.id.label("id"),
        AssetExit.asset_id.label("asset_id"),
        AssetExit.quantity.label("quantity"),
        literal("exit").label("type"),
        literal(None).label("supplier"),
        AssetExit.office.label("office"),
        AssetExit.created_at.label("created_at"),
        AssetExit.user_uuid.label("user_uuid"),
        AssetExit.exit_type.label("exit_type"),
        AssetExit.assigned_to.label("assigned_to"),
    )
    movements = union_all(entry_rows, exit_rows).subquery("inventory_movements")
    statement = select(movements).order_by(
        movements.c.created_at.desc(), movements.c.type, movements.c.id.desc()
    )
    return [dict(row) for row in session.exec(statement).mappings().all()]
