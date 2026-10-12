from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from tinydb import TinyDB
from tinydb.table import Table

from scripts import seed_incidents as seed_module
from app.incidents.manager_models import IncidentCreate
from app.incidents.manager_repository import IncidentRepository


ROOT = Path(__file__).parents[3]
DATASET = ROOT / "scripts" / "incidents-nexova.csv"
HEADER = (
    "ticket_id,date,client_company,category,description,agent_id,status,"
    "customer_email,satisfaction_score"
)


class IncidentSeedTests(unittest.TestCase):
    def run_main(self, csv_path: Path) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = seed_module.main(csv_path)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_missing_input_returns_nonzero_stderr_without_traceback(self) -> None:
        with TemporaryDirectory() as directory:
            code, stdout, stderr = self.run_main(Path(directory) / "missing.csv")

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("unable to read incidents CSV", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_malformed_csv_creates_no_database_or_partial_rows(self) -> None:
        malformed = (
            f"{HEADER}\n"
            'NXV-000001,2024-01-18,Acme,ACCESS,"bad"quote,AGT-01,OPEN,'
            "customer@example.com,"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "invalid.csv"
            database_path = root / "incidents.json"
            csv_path.write_text(malformed, encoding="utf-8")

            with mock.patch.dict(os.environ, {"INCIDENTS_DB_PATH": str(database_path)}):
                code, stdout, stderr = self.run_main(csv_path)

            self.assertEqual(code, 1)
            self.assertEqual(stdout, "")
            self.assertIn("row 2", stderr)
            self.assertNotIn("customer@example.com", stderr)
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(database_path.exists())

    def test_persistence_failure_returns_generic_error_without_traceback(self) -> None:
        with mock.patch.object(seed_module, "seed_incidents", side_effect=OSError("secret path")):
            code, stdout, stderr = self.run_main(DATASET)

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("unable to seed incidents", stderr)
        self.assertNotIn("secret path", stderr)
        self.assertNotIn("Traceback", stderr)

    def test_persistence_write_failure_leaves_prior_rows_and_reports_safe_error(self) -> None:
        original_insert = Table.insert
        incident_writes = 0
        persisted_before_failure: list[int] = []

        def insert_with_failure(table: Table, document: object) -> int:
            nonlocal incident_writes
            if table.name == "incidents":
                incident_writes += 1
                if incident_writes == 2:
                    raise OSError("database path leaked")
            document_id = original_insert(table, document)
            if table.name == "incidents" and incident_writes == 1:
                persisted_before_failure.append(len(table.all()))
            return document_id

        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "incidents.json"
            with mock.patch.dict(os.environ, {"INCIDENTS_DB_PATH": str(database_path)}):
                with mock.patch.object(
                    Table,
                    "insert",
                    autospec=True,
                    side_effect=insert_with_failure,
                ):
                    code, stdout, stderr = self.run_main(DATASET)

            self.assertEqual(persisted_before_failure, [1])
            self.assertTrue(database_path.exists())
            with TinyDB(database_path) as database:
                persisted_after_failure = database.table("incidents").all()
                persisted_seed_keys = database.table("incident_seed_keys").all()

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertIn("unable to seed incidents", stderr)
        self.assertNotIn("database path leaked", stderr)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(len(persisted_after_failure), 1)
        self.assertEqual(len(persisted_seed_keys), 1)

    def test_seed_is_idempotent_with_isolated_database(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "incidents.json"
            with mock.patch.dict(os.environ, {"INCIDENTS_DB_PATH": str(database_path)}):
                first = seed_module.seed_incidents(DATASET)
                second = seed_module.seed_incidents(DATASET)

        self.assertEqual(first["inserted"], 96)
        self.assertEqual(first["invalid_rows"], [18, 44, 87, 91])
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["total"], 96)

    def test_seed_preserves_manual_incident_and_counts_imported_rows(self) -> None:
        with TemporaryDirectory() as directory:
            database_path = Path(directory) / "incidents.json"
            with mock.patch.dict(os.environ, {"INCIDENTS_DB_PATH": str(database_path)}):
                with TinyDB(database_path) as database:
                    repository = IncidentRepository(database)
                    manual = repository.create(
                        IncidentCreate(
                            title="Manual incident",
                            description="Created before the historical import.",
                            category="candidate_issue",
                            status="resolved",
                            origin="customer",
                            branch="central",
                        )
                    )

                first = seed_module.seed_incidents(DATASET)
                second = seed_module.seed_incidents(DATASET)

                with TinyDB(database_path) as database:
                    repository = IncidentRepository(database)
                    incidents = repository.list()
                    manual_after = repository.get(manual.id)

            self.assertEqual(first["inserted"], 96)
            self.assertEqual(first["total"], 96)
            self.assertEqual(first["database_total"], 97)
            self.assertEqual(second["inserted"], 0)
            self.assertEqual(second["database_total"], 97)
            self.assertEqual(len(incidents), 97)
            self.assertIsNotNone(manual_after)
            self.assertEqual(manual_after.title, "Manual incident")

    def test_invalid_status_is_counted_as_invalid_row(self) -> None:
        row = seed_module.NormalizedIncidentRow(
            ticket_id="NXV-000001",
            date="2024-01-18",
            client_company="Acme",
            category="ACCESS",
            description="Valid support issue",
            agent_id="AGT-01",
            status="UNKNOWN",
            customer_email="customer@example.com",
            satisfaction_score=4,
        )

        self.assertIsNone(seed_module.transform_row(row))


if __name__ == "__main__":
    unittest.main()