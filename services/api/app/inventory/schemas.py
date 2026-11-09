"""HTTP request and response schemas, kept separate from ORM persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InventorySchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


InventoryOffice = Literal["Valencia", "Miami"]
InventoryCurrency = Literal["EUR", "USD"]


class ProgrammeCreate(InventorySchema):
    programme_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class ProgrammeResponse(ProgrammeCreate):
    pass


class AssetCreate(InventorySchema):
    name: str
    sku: str
    category: str
    office: InventoryOffice


class AssetResponse(AssetCreate):
    id: int
    currency: InventoryCurrency


class AssetWithStockResponse(AssetResponse):
    """Asset response for a future operation that has calculated its stock."""

    current_stock: float


class AssetEntryFields(InventorySchema):
    asset_id: int
    quantity: float = Field(gt=0, allow_inf_nan=False)
    supplier: str
    office: InventoryOffice


class AssetEntryCreate(AssetEntryFields):
    programme_id: str = Field(min_length=1)


class AssetEntryResponse(AssetEntryFields):
    id: int
    created_at: datetime
    user_uuid: UUID
    programme_id: str | None
    currency: InventoryCurrency


class AssetExitFields(InventorySchema):
    asset_id: int
    quantity: float = Field(gt=0, allow_inf_nan=False)
    exit_type: Literal["allocation", "consumption"]
    assigned_to: str | None = None
    office: InventoryOffice

    @model_validator(mode="after")
    def validate_assignee_for_exit_type(self) -> AssetExitFields:
        if self.exit_type == "allocation" and self.assigned_to is None:
            raise ValueError("assigned_to is required for allocation")
        if self.exit_type == "consumption" and self.assigned_to is not None:
            raise ValueError("assigned_to must be null for consumption")
        return self


class AssetExitCreate(AssetExitFields):
    programme_id: str = Field(min_length=1)


class AssetExitResponse(AssetExitFields):
    id: int
    created_at: datetime
    user_uuid: UUID
    programme_id: str | None
    currency: InventoryCurrency


class AssetEntryOrderResponse(AssetEntryResponse):
    """Entry variant of the unified inventory movement list."""

    type: Literal["entry"]


class AssetExitOrderResponse(AssetExitResponse):
    """Exit variant of the unified inventory movement list."""

    type: Literal["exit"]


InventoryOrderResponse = Annotated[
    Union[AssetEntryOrderResponse, AssetExitOrderResponse],
    Field(discriminator="type"),
]