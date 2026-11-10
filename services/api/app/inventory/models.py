"""SQLModel persistence models for inventory assets and movements."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Float, Index, JSON, Numeric, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Programme(SQLModel, table=True):
    __tablename__ = "programmes"

    programme_id: str = Field(primary_key=True, sa_type=String)
    name: str = Field(sa_type=String, nullable=False)


class Asset(SQLModel, table=True):
    """An inventory asset; stock is derived from its movement records."""

    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("sku", name="uq_assets_sku"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_type=String, nullable=False)
    sku: str = Field(sa_type=String, nullable=False)
    category: str = Field(sa_type=String, nullable=False)
    office: str = Field(sa_type=String, nullable=False)
    currency: str = Field(sa_type=String, nullable=False)

    entries: list["AssetEntry"] = Relationship(back_populates="asset")
    exits: list["AssetExit"] = Relationship(back_populates="asset")


class AssetEntry(SQLModel, table=True):
    """A positive stock-entry movement attributed to an authenticated user."""

    __tablename__ = "asset_entries"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_asset_entries_quantity_positive"),
        Index("uq_asset_entries_seed_key", "seed_key", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    seed_key: str | None = Field(default=None, sa_type=String, nullable=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    programme_id: str | None = Field(default=None, foreign_key="programmes.programme_id", index=True)
    quantity: float = Field(sa_column=Column(Float, nullable=False))
    # Nullable only to preserve historical receipts; new API writes require it.
    unit_cost: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    supplier: str = Field(sa_type=String, nullable=False)
    office: str = Field(sa_type=String, nullable=False)
    currency: str = Field(sa_type=String, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    user_uuid: UUID = Field(nullable=False)

    asset: "Asset" = Relationship(back_populates="entries")


class AssetExit(SQLModel, table=True):
    """A positive stock-exit movement attributed to an authenticated user."""

    __tablename__ = "asset_exits"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_asset_exits_quantity_positive"),
        CheckConstraint(
            "exit_type IN ('allocation', 'consumption')",
            name="ck_asset_exits_type",
        ),
        Index("uq_asset_exits_seed_key", "seed_key", unique=True),
        CheckConstraint(
            "(exit_type = 'allocation' AND assigned_to IS NOT NULL) OR "
            "(exit_type = 'consumption' AND assigned_to IS NULL)",
            name="ck_asset_exits_assigned_to_matches_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    seed_key: str | None = Field(default=None, sa_type=String, nullable=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    programme_id: str | None = Field(default=None, foreign_key="programmes.programme_id", index=True)
    quantity: float = Field(sa_column=Column(Float, nullable=False))
    exit_type: str = Field(sa_type=String, nullable=False)
    assigned_to: str | None = Field(default=None, sa_type=String, nullable=True)
    office: str = Field(sa_type=String, nullable=False)
    currency: str = Field(sa_type=String, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    user_uuid: UUID = Field(nullable=False)

    asset: "Asset" = Relationship(back_populates="exits")


class TelemetryOutboxEvent(SQLModel, table=True):
    """Durable business event captured atomically with its inventory movement."""

    __tablename__ = "telemetry_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'dead')",
            name="ck_telemetry_outbox_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_telemetry_outbox_attempt_count"),
        Index("ix_telemetry_outbox_claim", "status", "available_at", "timestamp"),
    )

    event_id: str = Field(primary_key=True, sa_type=String)
    event_type: str = Field(sa_type=String, nullable=False, index=True)
    timestamp: datetime = Field(nullable=False)
    source: str = Field(sa_type=String, nullable=False)
    tags: dict = Field(sa_column=Column(JSON, nullable=False))
    movement_type: str = Field(sa_type=String, nullable=False)
    movement_id: int = Field(nullable=False)
    status: str = Field(default="pending", sa_type=String, nullable=False, index=True)
    attempt_count: int = Field(default=0, nullable=False)
    locked_until: datetime | None = Field(default=None, nullable=True, index=True)
    lease_token: str | None = Field(default=None, sa_type=String, nullable=True)
    available_at: datetime = Field(default_factory=_utc_now, nullable=False, index=True)
    delivered_at: datetime | None = Field(default=None, nullable=True)
    dead_lettered_at: datetime | None = Field(default=None, nullable=True)
    last_error: str | None = Field(default=None, sa_type=String, nullable=True)


class StockThreshold(SQLModel, table=True):
    """Explicit per-product/office alert threshold; no production defaults."""

    __tablename__ = "inventory_stock_thresholds"
    __table_args__ = (
        UniqueConstraint("asset_id", "office", name="uq_inventory_threshold_asset_office"),
        CheckConstraint("threshold >= 0", name="ck_inventory_threshold_nonnegative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    office: str = Field(sa_type=String, nullable=False)
    threshold: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))


class InventoryValuation(SQLModel, table=True):
    """Current valued and unknown on-hand quantities and moving average."""

    __tablename__ = "inventory_valuations"
    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_inventory_valuation_asset"),
        CheckConstraint("valued_quantity >= 0", name="ck_valuation_valued_qty_nonnegative"),
        CheckConstraint("unvalued_quantity >= 0", name="ck_valuation_unvalued_qty_nonnegative"),
        CheckConstraint("average_cost >= 0", name="ck_valuation_average_cost_nonnegative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    valued_quantity: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 6), nullable=False))
    unvalued_quantity: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 6), nullable=False))
    average_cost: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(18, 6), nullable=False))


class InventoryValuationLedger(SQLModel, table=True):
    """Append-only audit of cost allocation and explicit stock regularization."""

    __tablename__ = "inventory_valuation_ledger"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_valuation_ledger_quantity_positive"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_valuation_ledger_cost_nonnegative"),
        Index("ix_valuation_ledger_asset_created", "asset_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    movement_type: str = Field(sa_type=String, nullable=False)
    movement_id: int = Field(nullable=False)
    quantity: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    unit_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    valued_quantity: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    unvalued_quantity: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    user_uuid: UUID = Field(nullable=False)
    reason: str | None = Field(default=None, sa_type=String, nullable=True)


class KitConfiguration(SQLModel, table=True):
    """Approved expected cost and variance trigger for one kit/office."""

    __tablename__ = "inventory_kit_configurations"
    __table_args__ = (
        UniqueConstraint("kit_asset_id", "office", name="uq_kit_configuration_asset_office"),
        CheckConstraint("expected_cost >= 0", name="ck_kit_expected_cost_nonnegative"),
        CheckConstraint("variance_threshold_percent >= 0", name="ck_kit_variance_threshold_nonnegative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    kit_asset_id: int = Field(foreign_key="assets.id", index=True)
    office: str = Field(sa_type=String, nullable=False)
    expected_cost: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    variance_threshold_percent: Decimal = Field(default=Decimal("10"), sa_column=Column(Numeric(10, 4), nullable=False))


class KitComponent(SQLModel, table=True):
    __tablename__ = "inventory_kit_components"
    __table_args__ = (
        UniqueConstraint("kit_asset_id", "component_asset_id", name="uq_kit_component_pair"),
        CheckConstraint("quantity_per_kit > 0", name="ck_kit_component_quantity_positive"),
        CheckConstraint("kit_asset_id != component_asset_id", name="ck_kit_component_not_self"),
    )

    id: int | None = Field(default=None, primary_key=True)
    kit_asset_id: int = Field(foreign_key="assets.id", index=True)
    component_asset_id: int = Field(foreign_key="assets.id", index=True)
    quantity_per_kit: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))


class KitPreparation(SQLModel, table=True):
    """Immutable cost snapshot for one atomic kit preparation."""

    __tablename__ = "inventory_kit_preparations"
    __table_args__ = (
        Index("uq_inventory_kit_preparation_idempotency_key", "idempotency_key", unique=True),
    )

    id: int | None = Field(default=None, primary_key=True)
    # Nullable to preserve historical preparations and optional for ordinary API calls.
    idempotency_key: str | None = Field(default=None, sa_type=String, nullable=True)
    kit_asset_id: int = Field(foreign_key="assets.id", index=True)
    programme_id: str = Field(foreign_key="programmes.programme_id", index=True)
    office: str = Field(sa_type=String, nullable=False)
    currency: str = Field(sa_type=String, nullable=False)
    kit_quantity: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    expected_cost: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    actual_cost: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 6), nullable=True))
    variance_percent: Decimal | None = Field(default=None, sa_column=Column(Numeric(10, 4), nullable=True))
    composition_snapshot: list = Field(sa_column=Column(JSON, nullable=False))
    incomplete_cost: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    user_uuid: UUID = Field(nullable=False)


class InventoryRegularization(SQLModel, table=True):
    """Single-admin approval that assigns cost to previously unknown stock."""

    __tablename__ = "inventory_regularizations"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_regularization_quantity_positive"),)

    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="assets.id", index=True)
    office: str = Field(sa_type=String, nullable=False)
    quantity: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    approved_unit_cost: Decimal = Field(sa_column=Column(Numeric(18, 6), nullable=False))
    reason: str = Field(sa_type=String, nullable=False)
    user_uuid: UUID = Field(nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)