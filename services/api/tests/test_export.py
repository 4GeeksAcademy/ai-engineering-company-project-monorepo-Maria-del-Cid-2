"""Tests for the Unit 5 safe aggregate CSV export."""

import csv
import io
import unittest
from pathlib import Path

from app.incidents.analysis import analyze_incidents_csv
from app.incidents.export import EXPORT_COLUMNS, export_analysis_csv


class IncidentExportTests(unittest.TestCase):
    def test_exports_aggregate_rows_with_expected_schema(self) -> None:
        result = analyze_incidents_csv(
            Path(__file__).parents[3] / "scripts" / "incidents-nexova.csv"
        )
        output = io.StringIO()

        export_analysis_csv(result, output)
        output.seek(0)
        rows = list(csv.DictReader(output))

        self.assertEqual(tuple(rows[0].keys()), EXPORT_COLUMNS)
        self.assertEqual(rows[0], {
            "metric": "total_records",
            "dimension": "all",
            "value": "100",
        })
        self.assertIn(
            {"metric": "valid_records", "dimension": "all", "value": "96"},
            rows,
        )
        self.assertIn(
            {"metric": "average_satisfaction", "dimension": "closed_tickets", "value": "3.84"},
            rows,
        )
        self.assertIn(
            {"metric": "records_by_category", "dimension": "TECHNICAL", "value": "28"},
            rows,
        )
        self.assertIn(
            {"metric": "records_by_status", "dimension": "CLOSED", "value": "56"},
            rows,
        )
        self.assertIn(
            {"metric": "satisfaction_distribution", "dimension": "4", "value": "22"},
            rows,
        )
        self.assertIn(
            {
                "metric": "invalid_by_type",
                "dimension": "invalid_email",
                "value": "1",
            },
            rows,
        )

    def test_export_never_contains_customer_email_or_raw_incident_fields(self) -> None:
        result = analyze_incidents_csv(
            Path(__file__).parents[3] / "scripts" / "incidents-nexova.csv"
        )
        output = io.StringIO()

        export_analysis_csv(result, output)
        csv_text = output.getvalue()

        self.assertNotIn("customer_email", csv_text)
        self.assertNotIn("@", csv_text)
        self.assertNotIn("ticket_id", csv_text)
        self.assertNotIn("description", csv_text)
        self.assertNotIn("customer@example.com", csv_text)

    def test_export_can_write_to_a_file(self) -> None:
        result = analyze_incidents_csv(
            Path(__file__).parents[3] / "scripts" / "incidents-nexova.csv"
        )
        destination = io.StringIO()

        export_analysis_csv(result, destination)

        self.assertEqual(destination.getvalue().splitlines()[0], "metric,dimension,value")


if __name__ == "__main__":
    unittest.main()
