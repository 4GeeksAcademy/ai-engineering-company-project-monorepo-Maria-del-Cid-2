"""Tests for Supplier Directory contracts and TinyDB initialisation."""

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from app.suppliers.database import create_database
from app.suppliers.models import Supplier, SupplierCreate, SupplierRateUpdate, SupplierStatusUpdate


VALID_SUPPLIER = {
    "name": "Workable",
    "country": "Spain",
    "categories": ["ats_software"],
    "monthly_rate": 299.0,
    "currency": "EUR",
    "status": "active",
}

# Payload de creación del cliente: el status NUNCA lo decide el cliente.
VALID_CREATE_PAYLOAD = {
    "name": "Workable",
    "country": "Spain",
    "categories": ["ats_software"],
    "monthly_rate": 299.0,
    "currency": "EUR",
}


class SupplierModelTests(unittest.TestCase):
    def test_valid_supplier_create_payload(self) -> None:
        supplier = SupplierCreate.model_validate(VALID_CREATE_PAYLOAD)

        self.assertEqual(supplier.country, "Spain")
        self.assertEqual(supplier.currency, "EUR")
        self.assertIsNone(getattr(supplier, "updated_at", None))
        # El cliente no envía status: no existe en SupplierCreate.
        self.assertNotIn("status", supplier.model_dump())

    def test_create_payload_cannot_set_status(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "status": "suspended"})

    def test_from_create_defaults_to_active_status(self) -> None:
        payload = SupplierCreate.model_validate(VALID_CREATE_PAYLOAD)
        supplier = Supplier.from_create(1, payload)

        self.assertEqual(supplier.status, "active")

    def test_from_create_can_preserve_seed_status(self) -> None:
        payload = SupplierCreate.model_validate(VALID_CREATE_PAYLOAD)
        supplier = Supplier.from_create(1, payload, status="suspended")

        self.assertEqual(supplier.status, "suspended")

    def test_supplier_generates_updated_at_and_id_only_for_response_model(self) -> None:
        payload = SupplierCreate.model_validate(VALID_CREATE_PAYLOAD)
        supplier = Supplier.from_create(1, payload)

        self.assertEqual(supplier.id, 1)
        self.assertIsInstance(supplier.updated_at, datetime)
        self.assertEqual(supplier.updated_at.tzinfo, timezone.utc)

    def test_updated_at_is_not_accepted_on_create(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "updated_at": datetime.now(timezone.utc)})

    def test_country_and_currency_must_match(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "currency": "USD"})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "country": "France"})

    def test_categories_must_be_valid_non_empty_and_unique(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "categories": []})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "categories": ["invalid_category"]})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "categories": ["ats_software", "ats_software"]})

    def test_status_and_rate_are_strictly_validated(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_CREATE_PAYLOAD, "monthly_rate": 0})

        with self.assertRaises(ValidationError):
            SupplierRateUpdate.model_validate({"monthly_rate": -1})

        with self.assertRaises(ValidationError):
            SupplierStatusUpdate.model_validate({"status": "deleted"})

    def test_optional_fields_are_supported(self) -> None:
        supplier = SupplierCreate.model_validate(
            {
                **VALID_CREATE_PAYLOAD,
                "contract_renewal_date": "2026-12-31",
                "contact_email": "manager@example.com",
                "notes": "Internal note",
            }
        )

        self.assertEqual(supplier.contract_renewal_date.isoformat(), "2026-12-31")
        self.assertEqual(str(supplier.contact_email), "manager@example.com")

    def test_tinydb_can_use_an_isolated_path(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "suppliers.json"
            database = create_database(database_path)
            database.insert({"id": 1, "name": "Workable"})
            database.close()

            reopened = create_database(database_path)
            self.assertEqual(reopened.all(), [{"id": 1, "name": "Workable"}])
            reopened.close()


if __name__ == "__main__":
    unittest.main()
