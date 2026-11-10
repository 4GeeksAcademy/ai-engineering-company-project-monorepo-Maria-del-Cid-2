"""Transactional inventory writes and their domain-level validation."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from contextlib import AbstractContextManager
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from .models import (
    Asset,
    AssetEntry,
    AssetExit,
    InventoryRegularization,
    InventoryValuation,
    InventoryValuationLedger,
    KitComponent,
    KitConfiguration,
    KitPreparation,
    Programme,
    StockThreshold,
    TelemetryOutboxEvent,
)
from .schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryResponse,
    AssetExitCreate,
    AssetExitResponse,
    AssetWithStockResponse,
    ProgrammeCreate,
    ProgrammeResponse,
    InventoryRegularizationCreate,
    KitConfigurationWrite,
    KitPreparationCreate,
    StockThresholdWrite,
)


OUTBOX_SOURCE = "/nexova/inventory"


def _transaction_scope(session: Session) -> AbstractContextManager[object]:
    """Join an orchestrating transaction with a savepoint when one is active."""
    return session.begin_nested() if session.in_transaction() else session.begin()


def _movement_event(
    event_type: str,
    movement_type: str,
    movement_id: int,
    tags: dict[str, object],
) -> TelemetryOutboxEvent:
    def json_safe(value: object) -> object:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {key: json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(item) for item in value]
        return value

    return TelemetryOutboxEvent(
        event_id=str(uuid4()),
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        source=OUTBOX_SOURCE,
        tags=json_safe(tags),
        movement_type=movement_type,
        movement_id=movement_id,
    )


def currency_for_office(office: str) -> str:
    return {"Valencia": "EUR", "Miami": "USD"}[office]


def create_programme(session: Session, payload: ProgrammeCreate) -> ProgrammeResponse:
    programme = Programme(**payload.model_dump())
    try:
        with _transaction_scope(session):
            session.add(programme)
            session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise InventoryConflict("A programme with this ID already exists.") from exc
    return ProgrammeResponse.model_validate(programme)


def create_asset(session: Session, payload: AssetCreate) -> AssetWithStockResponse:
    """Create a product; a new product has derived stock zero."""

    asset = Asset(**payload.model_dump(), currency=currency_for_office(payload.office))
    try:
        with _transaction_scope(session):
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

    movement = AssetEntry(**payload.model_dump(), currency=currency_for_office(payload.office), user_uuid=user_uuid)
    try:
        with _transaction_scope(session):
            asset = _require_asset(session, payload.asset_id, lock_for_update=True)
            _validate_movement(session, asset, payload.office, payload.programme_id)
            valuation = _valuation_for_asset(session, asset.id)
            incoming_quantity = _decimal(payload.quantity)
            incoming_cost = _decimal(payload.unit_cost)
            previous_valued = _decimal(valuation.valued_quantity)
            new_valued = previous_valued + incoming_quantity
            valuation.average_cost = (
                previous_valued * _decimal(valuation.average_cost) + incoming_quantity * incoming_cost
            ) / new_valued
            valuation.valued_quantity = new_valued
            session.add(movement)
            session.flush()
            session.add(InventoryValuationLedger(
                asset_id=asset.id, movement_type="entry", movement_id=movement.id,
                quantity=incoming_quantity, unit_cost=incoming_cost,
                valued_quantity=incoming_quantity, unvalued_quantity=Decimal("0"),
                user_uuid=user_uuid,
            ))
            session.add(
                _movement_event(
                    "inbound_order_created",
                    "entry",
                    movement.id,
                    {
                        "product_id": asset.id,
                        "product_sku": asset.sku,
                        "product_category": asset.category,
                        "programme_id": movement.programme_id,
                        "quantity": movement.quantity,
                        "supplier": movement.supplier,
                        "office": movement.office,
                        "currency": movement.currency,
                        "unit_cost": movement.unit_cost,
                        "user_uuid": str(movement.user_uuid),
                    },
                )
            )
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

    movement = AssetExit(**payload.model_dump(), currency=currency_for_office(payload.office), user_uuid=user_uuid)
    try:
        with _transaction_scope(session):
            _set_postgres_read_committed(session)
            asset = _require_asset(session, payload.asset_id, lock_for_update=True)
            _validate_movement(session, asset, payload.office, payload.programme_id)
            available_stock = _stock_for_asset(session, payload.asset_id)
            if payload.quantity > available_stock:
                raise InsufficientStock("Insufficient stock for this outbound movement.")

            valuation = _valuation_for_asset(session, asset.id)
            quantity = _decimal(payload.quantity)
            before_stock = _decimal(available_stock)
            unvalued_used = min(quantity, _decimal(valuation.unvalued_quantity))
            valued_used = quantity - unvalued_used
            valuation.unvalued_quantity = _decimal(valuation.unvalued_quantity) - unvalued_used
            valuation.valued_quantity = _decimal(valuation.valued_quantity) - valued_used
            average_cost = _decimal(valuation.average_cost)
            if valuation.valued_quantity == 0:
                valuation.average_cost = Decimal("0")

            session.add(movement)
            session.flush()
            session.add(InventoryValuationLedger(
                asset_id=asset.id, movement_type="exit", movement_id=movement.id,
                quantity=quantity, unit_cost=average_cost if valued_used else None,
                valued_quantity=valued_used, unvalued_quantity=unvalued_used,
                user_uuid=user_uuid,
            ))
            session.add(
                _movement_event(
                    "outbound_order_created",
                    "exit",
                    movement.id,
                    {
                        "product_id": asset.id,
                        "product_sku": asset.sku,
                        "product_category": asset.category,
                        "programme_id": movement.programme_id,
                        "quantity": movement.quantity,
                        "exit_type": movement.exit_type,
                        "office": movement.office,
                        "currency": movement.currency,
                        "user_uuid": str(movement.user_uuid),
                    },
                )
            )
            _emit_threshold_if_crossed(
                session, asset, before_stock, before_stock - quantity,
                movement.programme_id, movement.id,
            )
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


def _decimal(value: object) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _valuation_for_asset(session: Session, asset_id: int) -> InventoryValuation:
    """Use migration state or lazily mark pre-migration net stock unknown."""
    statement = select(InventoryValuation).where(InventoryValuation.asset_id == asset_id)
    if session.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update()
    result = session.exec(statement).first()
    if result is not None:
        return result
    stock = _decimal(_stock_for_asset(session, asset_id))
    if stock < 0:
        raise InventoryConflict("Historical stock is negative; valuation is unavailable.")
    valuation = InventoryValuation(
        asset_id=asset_id, valued_quantity=Decimal("0"),
        unvalued_quantity=stock, average_cost=Decimal("0"),
    )
    session.add(valuation)
    session.flush()
    return valuation


def _emit_threshold_if_crossed(
    session: Session,
    asset: Asset,
    before_stock: Decimal,
    after_stock: Decimal,
    programme_id: str | None,
    movement_id: int,
) -> None:
    if programme_id is None or asset.id is None:
        return
    threshold = session.exec(select(StockThreshold).where(
        StockThreshold.asset_id == asset.id, StockThreshold.office == asset.office,
    )).first()
    if threshold is None:
        return
    limit = _decimal(threshold.threshold)
    if before_stock >= limit and after_stock < limit:
        session.add(_movement_event(
            "stock_threshold_triggered", "exit", movement_id,
            {
                "product_id": asset.id, "product_sku": asset.sku,
                "product_category": asset.category, "programme_id": programme_id,
                "office": asset.office, "currency": asset.currency,
                "current_stock": float(after_stock),
                "threshold": float(limit), "stock_level": "out" if after_stock <= 0 else "low",
                "movement_id": movement_id,
            },
        ))


def configure_stock_threshold(session: Session, payload: StockThresholdWrite) -> StockThreshold:
    with _transaction_scope(session):
        asset = _require_asset(session, payload.asset_id)
        if asset.office != payload.office:
            raise HTTPException(status_code=422, detail="Threshold office must match product office.")
        item = session.exec(select(StockThreshold).where(
            StockThreshold.asset_id == asset.id, StockThreshold.office == payload.office,
        )).first()
        if item is None:
            item = StockThreshold(**payload.model_dump())
            session.add(item)
        else:
            item.threshold = payload.threshold
        session.flush()
    return item


def configure_kit(session: Session, payload: KitConfigurationWrite) -> KitConfiguration:
    with _transaction_scope(session):
        kit = _require_asset(session, payload.kit_asset_id)
        if kit.office != payload.office:
            raise HTTPException(status_code=422, detail="Kit office must match product office.")
        component_ids = sorted({component.component_asset_id for component in payload.components})
        if kit.id in component_ids or len(component_ids) != len(payload.components):
            raise HTTPException(status_code=422, detail="Kit components must be unique and cannot include the kit itself.")
        components: list[tuple[Asset, KitComponent]] = []
        for component_payload in sorted(payload.components, key=lambda item: item.component_asset_id):
            component = _require_asset(session, component_payload.component_asset_id)
            if component.office != kit.office:
                raise HTTPException(status_code=422, detail="Kit components must share the kit office and currency.")
            components.append((component, KitComponent(
                kit_asset_id=kit.id, component_asset_id=component.id,
                quantity_per_kit=component_payload.quantity_per_kit,
            )))
        config = session.exec(select(KitConfiguration).where(
            KitConfiguration.kit_asset_id == kit.id, KitConfiguration.office == kit.office,
        )).first()
        if config is None:
            config = KitConfiguration(
                kit_asset_id=kit.id, office=kit.office,
                expected_cost=payload.expected_cost,
                variance_threshold_percent=payload.variance_threshold_percent,
            )
            session.add(config)
        else:
            config.expected_cost = payload.expected_cost
            config.variance_threshold_percent = payload.variance_threshold_percent
            for old in session.exec(select(KitComponent).where(KitComponent.kit_asset_id == kit.id)).all():
                session.delete(old)
            session.flush()
        session.add_all([row for _asset, row in components])
        session.flush()
    return config


def prepare_kit(
    session: Session, payload: KitPreparationCreate, *, user_uuid: UUID,
) -> KitPreparation:
    """Atomically consume one approved composition and snapshot its costs."""
    try:
        with _transaction_scope(session):
            _set_postgres_read_committed(session)
            kit = _require_asset(session, payload.kit_asset_id, lock_for_update=True)
            if payload.idempotency_key is not None:
                existing_preparation = session.exec(select(KitPreparation).where(
                    KitPreparation.idempotency_key == payload.idempotency_key,
                )).first()
                if existing_preparation is not None:
                    if (
                        existing_preparation.kit_asset_id != payload.kit_asset_id
                        or existing_preparation.office != payload.office
                        or existing_preparation.programme_id != payload.programme_id
                        or _decimal(existing_preparation.kit_quantity) != _decimal(payload.quantity)
                    ):
                        raise InventoryConflict("The kit idempotency key was already used for another request.")
                    return existing_preparation
            if kit.office != payload.office:
                raise HTTPException(status_code=422, detail="Preparation office must match kit office.")
            if session.get(Programme, payload.programme_id) is None:
                raise HTTPException(status_code=404, detail="Programme not found.")
            config_statement = select(KitConfiguration).where(
                KitConfiguration.kit_asset_id == kit.id, KitConfiguration.office == kit.office,
            )
            if session.get_bind().dialect.name == "postgresql":
                config_statement = config_statement.with_for_update()
            config = session.exec(config_statement).first()
            if config is None:
                raise HTTPException(status_code=404, detail="Kit configuration not found.")
            components = session.exec(select(KitComponent).where(
                KitComponent.kit_asset_id == kit.id,
            ).order_by(KitComponent.component_asset_id)).all()
            if not components:
                raise HTTPException(status_code=422, detail="Kit composition is empty.")
            assets = [_require_asset(session, row.component_asset_id, lock_for_update=True) for row in components]
            composition: list[dict[str, object]] = []
            actual_cost = Decimal("0")
            incomplete = False
            for component, asset in zip(components, assets, strict=True):
                quantity = _decimal(component.quantity_per_kit) * payload.quantity
                available = _decimal(_stock_for_asset(session, asset.id))
                if quantity > available:
                    raise InsufficientStock(f"Insufficient stock for component {asset.sku}.")
                valuation = _valuation_for_asset(session, asset.id)
                unvalued_used = min(quantity, _decimal(valuation.unvalued_quantity))
                valued_used = quantity - unvalued_used
                unit_cost = _decimal(valuation.average_cost)
                if unvalued_used:
                    incomplete = True
                else:
                    actual_cost += valued_used * unit_cost
                valuation.unvalued_quantity = _decimal(valuation.unvalued_quantity) - unvalued_used
                valuation.valued_quantity = _decimal(valuation.valued_quantity) - valued_used
                if valuation.valued_quantity == 0:
                    valuation.average_cost = Decimal("0")
                movement = AssetExit(
                    asset_id=asset.id, programme_id=payload.programme_id,
                    quantity=quantity, exit_type="consumption", assigned_to=None,
                    office=kit.office, currency=kit.currency, user_uuid=user_uuid,
                    seed_key=(f"{payload.idempotency_key}:component:{asset.sku}" if payload.idempotency_key else None),
                )
                session.add(movement)
                session.flush()
                session.add(InventoryValuationLedger(
                    asset_id=asset.id, movement_type="exit", movement_id=movement.id,
                    quantity=quantity, unit_cost=unit_cost if valued_used else None,
                    valued_quantity=valued_used, unvalued_quantity=unvalued_used,
                    user_uuid=user_uuid,
                ))
                session.add(_movement_event("outbound_order_created", "exit", movement.id, {
                    "product_id": asset.id, "product_sku": asset.sku,
                    "product_category": asset.category, "programme_id": payload.programme_id,
                    "quantity": quantity, "exit_type": "consumption", "office": kit.office,
                    "currency": kit.currency, "user_uuid": str(user_uuid),
                }))
                before = available
                _emit_threshold_if_crossed(session, asset, before, before - quantity, payload.programme_id, movement.id)
                composition.append({
                    "product_id": asset.id, "sku": asset.sku,
                    "quantity": str(quantity), "valued_quantity": str(valued_used),
                    "unvalued_quantity": str(unvalued_used),
                    "unit_cost": str(unit_cost) if valued_used else None,
                })

            actual = None if incomplete else actual_cost
            expected_per_kit = _decimal(config.expected_cost)
            actual_per_kit = actual / payload.quantity if actual is not None else None
            variance = None
            if actual_per_kit is not None and expected_per_kit > 0:
                variance = (actual_per_kit - expected_per_kit) / expected_per_kit * Decimal("100")
            preparation = KitPreparation(
                idempotency_key=payload.idempotency_key,
                kit_asset_id=kit.id, programme_id=payload.programme_id,
                office=kit.office, currency=kit.currency, kit_quantity=payload.quantity,
                expected_cost=expected_per_kit, actual_cost=actual_per_kit,
                variance_percent=variance, composition_snapshot=composition,
                incomplete_cost=incomplete, user_uuid=user_uuid,
            )
            session.add(preparation)
            session.flush()
            if variance is not None and variance > _decimal(config.variance_threshold_percent):
                session.add(_movement_event("kit_cost_variance_detected", "kit_preparation", preparation.id, {
                    "product_id": kit.id, "product_sku": kit.sku,
                    "product_category": kit.category, "programme_id": payload.programme_id,
                    "kit_composition": [item["sku"] for item in composition],
                    "expected_cost": float(expected_per_kit), "actual_cost": float(actual_per_kit),
                    "variance_percent": float(variance), "currency": kit.currency,
                    "office": kit.office, "preparation_id": preparation.id,
                }))
    except IntegrityError as exc:
        session.rollback()
        raise InventoryConflict("The kit preparation conflicts with stored data.") from exc
    return preparation


def create_inventory_regularization(
    session: Session, payload: InventoryRegularizationCreate, *, user_uuid: UUID,
) -> InventoryRegularization:
    with _transaction_scope(session):
        asset = _require_asset(session, payload.asset_id, lock_for_update=True)
        if asset.office != payload.office:
            raise HTTPException(status_code=422, detail="Regularization office must match product office.")
        valuation = _valuation_for_asset(session, asset.id)
        quantity = _decimal(payload.quantity)
        if quantity > _decimal(valuation.unvalued_quantity):
            raise HTTPException(status_code=422, detail="Regularization cannot exceed currently unvalued stock.")
        row = InventoryRegularization(**payload.model_dump(), user_uuid=user_uuid)
        session.add(row)
        session.flush()
        cost = _decimal(payload.approved_unit_cost)
        old_qty, new_qty = _decimal(valuation.valued_quantity), _decimal(valuation.valued_quantity) + quantity
        valuation.average_cost = (old_qty * _decimal(valuation.average_cost) + quantity * cost) / new_qty
        valuation.valued_quantity = new_qty
        valuation.unvalued_quantity = _decimal(valuation.unvalued_quantity) - quantity
        session.add(InventoryValuationLedger(
            asset_id=asset.id, movement_type="regularization", movement_id=row.id,
            quantity=quantity, unit_cost=cost, valued_quantity=quantity,
            unvalued_quantity=Decimal("0"), user_uuid=user_uuid, reason=payload.reason,
        ))
    return row


def _validate_movement(session: Session, asset: Asset, office: str, programme_id: str) -> None:
    if asset.office != office:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Movement office must match product office.")
    if session.get(Programme, programme_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programme not found.")


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
    ).one()
    exits = session.exec(
        select(func.coalesce(func.sum(AssetExit.quantity), 0.0)).where(
            AssetExit.asset_id == asset_id
        )
    ).one()
    return float(entries) - float(exits)