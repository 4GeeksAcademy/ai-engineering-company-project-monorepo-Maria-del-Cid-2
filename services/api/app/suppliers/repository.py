"""TinyDB repository operations for Supplier Directory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tinydb import Query, TinyDB
from tinydb.table import Document

from .models import Supplier, SupplierCreate


class SupplierRepository:
    """Persistence adapter that keeps TinyDB details out of the API router."""

    def __init__(self, database: TinyDB) -> None:
        self.database = database

    def list(self, country: str | None = None, category: str | None = None) -> list[Supplier]:
        records = self.database.all()
        suppliers = [Supplier.model_validate(record) for record in records]
        if country is not None:
            suppliers = [supplier for supplier in suppliers if supplier.country == country]
        if category is not None:
            suppliers = [
                supplier for supplier in suppliers if category in supplier.categories
            ]
        return suppliers

    def get(self, supplier_id: int) -> Supplier | None:
        record = self.database.get(doc_id=supplier_id)
        return Supplier.model_validate(record) if record is not None else None

    def create(self, payload: SupplierCreate) -> Supplier:
        supplier_id = max((record.doc_id for record in self.database), default=0) + 1
        supplier = Supplier.from_create(supplier_id, payload)
        self.database.insert(Document(supplier.model_dump(mode="json"), doc_id=supplier_id))
        return supplier

    def update_rate(self, supplier_id: int, monthly_rate: float) -> Supplier | None:
        supplier = self.get(supplier_id)
        if supplier is None:
            return None
        updated = supplier.model_copy(
            update={
                "monthly_rate": monthly_rate,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self.database.update(updated.model_dump(mode="json"), doc_ids=[supplier_id])
        return updated

    def update_status(self, supplier_id: int, status: str) -> Supplier | None:
        supplier = self.get(supplier_id)
        if supplier is None:
            return None
        updated = supplier.model_copy(update={"status": status})
        self.database.update(updated.model_dump(mode="json"), doc_ids=[supplier_id])
        return updated

    def delete(self, supplier_id: int) -> bool:
        return bool(self.database.remove(doc_ids=[supplier_id]))
