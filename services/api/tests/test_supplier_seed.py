"""Tests for the Supplier Directory seed command."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.suppliers.database import create_database
from app.suppliers.seed import SUPPLIERS_SEED, seed_suppliers


class SupplierSeedTests(unittest.TestCase):
    def test_empty_database_receives_exactly_fifteen_valid_suppliers(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database = create_database(Path(temporary_directory) / "suppliers.json")
            try:
                inserted = seed_suppliers(database)

                self.assertEqual(inserted, 15)
                self.assertEqual(len(database), 15)
                self.assertEqual(
                    {supplier["name"] for supplier in database.all()},
                    {supplier["name"] for supplier in SUPPLIERS_SEED},
                )
                self.assertTrue(all(supplier["updated_at"] for supplier in database.all()))
            finally:
                database.close()

    def test_running_seed_twice_does_not_create_duplicates(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            database = create_database(Path(temporary_directory) / "suppliers.json")
            try:
                self.assertEqual(seed_suppliers(database), 15)
                self.assertEqual(seed_suppliers(database), 0)
                self.assertEqual(len(database), 15)
                self.assertEqual(
                    len({supplier["name"] for supplier in database.all()}),
                    15,
                )
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
