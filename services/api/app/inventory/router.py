"""Authenticated read-only inventory endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.dependencies import get_current_user
from app.inventory.database import get_session
from app.inventory.queries import (
    get_asset_with_stock,
    list_assets_with_stock,
    list_inventory_orders,
)
from app.inventory.schemas import (
    AssetEntryOrderResponse,
    AssetExitOrderResponse,
    AssetWithStockResponse,
    InventoryOrderResponse,
)

router = APIRouter(
    prefix="/api/inventory",
    tags=["inventory"],
    dependencies=[Depends(get_current_user)],
)

SessionDependency = Annotated[Session, Depends(get_session)]


def _asset_response(asset: BaseModel, current_stock: float) -> AssetWithStockResponse:
    return AssetWithStockResponse.model_validate(
        {**asset.model_dump(), "current_stock": current_stock}
    )


@router.get("/products", response_model=list[AssetWithStockResponse])
def get_inventory_products(session: SessionDependency) -> list[AssetWithStockResponse]:
    """List inventory products with stock derived from movement sums."""

    return [
        _asset_response(asset, stock)
        for asset, stock in list_assets_with_stock(session)
    ]


@router.get(
    "/products/{asset_id}",
    response_model=AssetWithStockResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Product not found"}},
)
def get_inventory_product(
    asset_id: int,
    session: SessionDependency,
) -> AssetWithStockResponse:
    """Get one inventory product with derived stock."""

    result = get_asset_with_stock(session, asset_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    asset, stock = result
    return _asset_response(asset, stock)


@router.get("/orders", response_model=list[InventoryOrderResponse])
def get_inventory_orders(session: SessionDependency) -> list[InventoryOrderResponse]:
    """List entry and exit movements as a discriminated union."""

    responses: list[InventoryOrderResponse] = []
    for row in list_inventory_orders(session):
        movement_type = row.pop("type")
        if movement_type == "entry":
            row.pop("exit_type")
            row.pop("assigned_to")
            responses.append(AssetEntryOrderResponse(type="entry", **row))
        else:
            row.pop("supplier")
            responses.append(AssetExitOrderResponse(type="exit", **row))
    return responses
