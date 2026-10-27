"""Authenticated read-only inventory endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.models import User
from app.auth.dependencies import get_current_user
from app.inventory.database import get_session
from app.inventory.operations import (
    InsufficientStock,
    InventoryConflict,
    create_asset,
    create_inbound,
    create_outbound,
)
from app.inventory.queries import (
    get_asset_with_stock,
    list_assets_with_stock,
    list_inventory_orders,
)
from app.inventory.schemas import (
    AssetCreate,
    AssetEntryCreate,
    AssetEntryOrderResponse,
    AssetEntryResponse,
    AssetExitCreate,
    AssetExitOrderResponse,
    AssetExitResponse,
    AssetWithStockResponse,
    InventoryOrderResponse,
)
from app.cache import TTLCache

CACHE_TTL_PRODUCTS: float = 30.0
_products_cache: TTLCache[list[AssetWithStockResponse]] = TTLCache(
    default_ttl=CACHE_TTL_PRODUCTS
)

router = APIRouter(
    prefix="/api/inventory",
    tags=["inventory"],
    dependencies=[Depends(get_current_user)],
)

SessionDependency = Annotated[Session, Depends(get_session)]
CurrentUserDependency = Annotated[User, Depends(get_current_user)]


def _asset_response(asset: BaseModel, current_stock: float) -> AssetWithStockResponse:
    return AssetWithStockResponse.model_validate(
        {**asset.model_dump(), "current_stock": current_stock}
    )


@router.get("/products", response_model=list[AssetWithStockResponse])
def get_inventory_products(session: SessionDependency) -> list[AssetWithStockResponse]:
    """List inventory products with stock derived from movement sums.

    Results are cached in memory for ``{CACHE_TTL_PRODUCTS}`` seconds to
    reduce repeated database aggregation queries.
    """

    cached = _products_cache.get("list")
    if cached is not None:
        return cached

    result = [
        _asset_response(asset, stock)
        for asset, stock in list_assets_with_stock(session)
    ]
    _products_cache.set("list", result)
    return result


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


@router.post(
    "/products",
    response_model=AssetWithStockResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": "Duplicate product SKU"}},
)
def post_inventory_product(
    payload: AssetCreate,
    session: SessionDependency,
) -> AssetWithStockResponse:
    """Create a product; callers cannot set identity or stock."""

    try:
        result = create_asset(session, payload)
        _products_cache.invalidate("list")
        return result
    except InventoryConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/orders/inbound",
    response_model=AssetEntryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Product not found"},
        status.HTTP_409_CONFLICT: {"description": "Inventory integrity conflict"},
        status.HTTP_428_PRECONDITION_REQUIRED: {"description": "User UUID required"},
    },
)
def post_inventory_inbound(
    payload: AssetEntryCreate,
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> AssetEntryResponse:
    """Record an inbound movement attributed to the authenticated user."""

    user_uuid = _require_user_uuid(current_user)
    try:
        result = create_inbound(session, payload, user_uuid=user_uuid)
        _products_cache.invalidate("list")
        return result
    except InventoryConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/orders/outbound",
    response_model=AssetExitResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Insufficient stock"},
        status.HTTP_404_NOT_FOUND: {"description": "Product not found"},
        status.HTTP_409_CONFLICT: {"description": "Inventory integrity conflict"},
        status.HTTP_428_PRECONDITION_REQUIRED: {"description": "User UUID required"},
    },
)
def post_inventory_outbound(
    payload: AssetExitCreate,
    session: SessionDependency,
    current_user: CurrentUserDependency,
) -> AssetExitResponse:
    """Record an outbound movement if enough derived stock is available."""

    user_uuid = _require_user_uuid(current_user)
    try:
        result = create_outbound(session, payload, user_uuid=user_uuid)
        _products_cache.invalidate("list")
        return result
    except InsufficientStock as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except InventoryConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _require_user_uuid(current_user: User):
    """Reject legacy authenticated users until UUID assignment is approved."""

    if current_user.user_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="The authenticated user must have a persistent UUID to write inventory movements.",
        )
    return current_user.user_uuid
