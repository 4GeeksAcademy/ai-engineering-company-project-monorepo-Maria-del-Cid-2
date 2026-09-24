"""Tests for the Unit 6 command-line interface."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
CLI = ROOT / "scripts" / "analyze.py"
DATASET = ROOT / "scripts" / "incidents-nexova.csv"


class IncidentCliTests(unittest.TestCase):
    def run_cli(self, csv_path: Path, answer: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), str(csv_path)],
            input=f"{answer}\n",
            text=True,
            capture_output=True,
            cwd=cwd or ROOT,
            check=False,
        )

    def test_valid_csv_displays_aggregate_report_without_emails(self) -> None:
        completed = self.run_cli(DATASET, "n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("TOTAL RECORDS IN FILE .......... 100", completed.stdout)
        self.assertIn("Valid records ................ 96", completed.stdout)
        self.assertIn("Invalid / incomplete .......... 4", completed.stdout)
        self.assertIn("Average score: 3.84 / 5.00", completed.stdout)
        self.assertIn("Export results to CSV? [y / n]:", completed.stdout)
        self.assertNotIn("@", completed.stdout)
        self.assertNotIn("customer_email", completed.stdout)

    def test_invalid_path_returns_error(self) -> None:
        completed = self.run_cli(ROOT / "does-not-exist.csv", "n")

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Error: unable to analyze CSV:", completed.stderr)
        self.assertNotIn("@", completed.stdout + completed.stderr)

    def test_n_does_not_create_results_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            completed = self.run_cli(DATASET, "n", cwd=output_dir)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse((output_dir / "results.csv").exists())

    def test_y_creates_aggregate_results_csv_without_emails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            completed = self.run_cli(DATASET, "y", cwd=output_dir)
            results_path = output_dir / "results.csv"

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(results_path.exists())
            self.assertIn("Results exported to results.csv", completed.stdout)
            content = results_path.read_text(encoding="utf-8")
            self.assertNotIn("customer_email", content)
            self.assertNotIn("@", content)
            self.assertNotIn("ticket_id", content)
            with results_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertIn(
                {"metric": "total_records", "dimension": "all", "value": "100"},
                rows,
            )
            self.assertIn(
                {"metric": "average_satisfaction", "dimension": "closed_tickets", "value": "3.84"},
                rows,
            )


if __name__ == "__main__":
    unittest.main()
