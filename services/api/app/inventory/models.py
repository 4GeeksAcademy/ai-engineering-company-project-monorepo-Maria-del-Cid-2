"""SQLModel persistence models for inventory assets and movements."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, Float, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Asset(SQLModel, table=True):
    """An inventory asset; stock is derived from its movement records."""

    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("sku", name="uq_assets_sku"),)

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_type=String, nullable=False)
    sku: str = Field(sa_type=String, nullable=False)
    category: str = Field(sa_type=String, nullable=False)
    office: str = Field(sa_type=String, nullable=False)

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
    quantity: float = Field(sa_column=Column(Float, nullable=False))
    supplier: str = Field(sa_type=String, nullable=False)
    office: str = Field(sa_type=String, nullable=False)
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
    quantity: float = Field(sa_column=Column(Float, nullable=False))
    exit_type: str = Field(sa_type=String, nullable=False)
    assigned_to: str | None = Field(default=None, sa_type=String, nullable=True)
    office: str = Field(sa_type=String, nullable=False)
    created_at: datetime = Field(default_factory=_utc_now, nullable=False)
    user_uuid: UUID = Field(nullable=False)

    asset: "Asset" = Relationship(back_populates="exits")