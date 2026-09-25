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


class SupplierModelTests(unittest.TestCase):
    def test_valid_supplier_create_payload(self) -> None:
        supplier = SupplierCreate.model_validate(VALID_SUPPLIER)

        self.assertEqual(supplier.country, "Spain")
        self.assertEqual(supplier.currency, "EUR")
        self.assertIsNone(getattr(supplier, "updated_at", None))

    def test_supplier_generates_updated_at_and_id_only_for_response_model(self) -> None:
        payload = SupplierCreate.model_validate(VALID_SUPPLIER)
        supplier = Supplier.from_create(1, payload)

        self.assertEqual(supplier.id, 1)
        self.assertIsInstance(supplier.updated_at, datetime)
        self.assertEqual(supplier.updated_at.tzinfo, timezone.utc)

    def test_updated_at_is_not_accepted_on_create(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "updated_at": datetime.now(timezone.utc)})

    def test_country_and_currency_must_match(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "currency": "USD"})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "country": "France"})

    def test_categories_must_be_valid_non_empty_and_unique(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "categories": []})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "categories": ["invalid_category"]})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "categories": ["ats_software", "ats_software"]})

    def test_status_and_rate_are_strictly_validated(self) -> None:
        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "status": "deleted"})

        with self.assertRaises(ValidationError):
            SupplierCreate.model_validate({**VALID_SUPPLIER, "monthly_rate": 0})

        with self.assertRaises(ValidationError):
            SupplierRateUpdate.model_validate({"monthly_rate": -1})

        with self.assertRaises(ValidationError):
            SupplierStatusUpdate.model_validate({"status": "deleted"})

    def test_optional_fields_are_supported(self) -> None:
        supplier = SupplierCreate.model_validate(
            {
                **VALID_SUPPLIER,
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
