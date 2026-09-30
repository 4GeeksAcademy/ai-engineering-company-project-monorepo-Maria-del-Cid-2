"""Supplier Directory HTTP endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import get_current_user
from app.auth.models import User
from .database import get_database
from .models import Category, Country, Supplier, SupplierCreate, SupplierRateUpdate, SupplierStatusUpdate
from .repository import SupplierRepository

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def get_repository() -> SupplierRepository:
    """Provide a repository backed by the configured TinyDB file."""

    database = get_database()
    try:
        yield SupplierRepository(database)
    finally:
        database.close()


@router.post("", response_model=Supplier, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> Supplier:
    return repository.create(payload)


@router.get("", response_model=list[Supplier])
def list_suppliers(
    country: Country | None = Query(default=None),
    category: Category | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> list[Supplier]:
    return repository.list(country=country, category=category)


@router.get("/{supplier_id}", response_model=Supplier)
def get_supplier(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> Supplier:
    supplier = repository.get(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/{supplier_id}/rate", response_model=Supplier)
def update_supplier_rate(
    supplier_id: int,
    payload: SupplierRateUpdate,
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> Supplier:
    supplier = repository.update_rate(supplier_id, payload.monthly_rate)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.patch("/{supplier_id}/status", response_model=Supplier)
def update_supplier_status(
    supplier_id: int,
    payload: SupplierStatusUpdate,
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> Supplier:
    supplier = repository.update_status(supplier_id, payload.status)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: int,
    current_user: User = Depends(get_current_user),
    repository: SupplierRepository = Depends(get_repository),
) -> None:
    if not repository.delete(supplier_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
