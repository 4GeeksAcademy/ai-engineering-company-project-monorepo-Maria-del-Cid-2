"""SQLModel persistence models for inventory assets and movements."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Float, Index, JSON, String, UniqueConstraint
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
    )

    id: int | None = Field(default=None, primary_key=True)
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
        CheckConstraint(
            "(exit_type = 'allocation' AND assigned_to IS NOT NULL) OR "
            "(exit_type = 'consumption' AND assigned_to IS NULL)",
            name="ck_asset_exits_assigned_to_matches_type",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
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