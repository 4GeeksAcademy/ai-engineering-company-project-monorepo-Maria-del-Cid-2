"""Tests for the Unit 4 incident analysis engine."""

import unittest
from pathlib import Path

from app.incidents.analysis import analyze_incidents, analyze_incidents_csv
from app.incidents.constants import (
    IncidentCategory,
    IncidentStatus,
    ValidationErrorCode,
)
from app.incidents.csv_reader import NormalizedIncidentRow


class IncidentAnalysisTests(unittest.TestCase):
    def make_row(self, **changes: object) -> NormalizedIncidentRow:
        values: dict[str, object] = {
            "ticket_id": "NXV-000001",
            "date": "2024-01-18",
            "client_company": "Acme",
            "category": "ACCESS",
            "description": "A valid support issue",
            "agent_id": "AGT-08",
            "status": "CLOSED",
            "customer_email": "customer@example.com",
            "satisfaction_score": 4,
        }
        values.update(changes)
        return NormalizedIncidentRow(**values)

    def test_aggregates_valid_rows_and_error_counts(self) -> None:
        result = analyze_incidents(
            [
                self.make_row(category="ACCESS", status="CLOSED", satisfaction_score=5),
                self.make_row(category="BILLING", status="OPEN", satisfaction_score=None),
                self.make_row(customer_email="bad-email"),
                self.make_row(client_company=""),
            ]
        )

        self.assertEqual(result.total_records, 4)
        self.assertEqual(result.valid_records, 2)
        self.assertEqual(result.invalid_records, 2)
        self.assertEqual(result.by_category, {IncidentCategory.ACCESS: 1, IncidentCategory.BILLING: 1})
        self.assertEqual(result.by_status, {IncidentStatus.CLOSED: 1, IncidentStatus.OPEN: 1})
        self.assertEqual(result.satisfaction_distribution, {5: 1})
        self.assertEqual(result.average_satisfaction, 5.0)
        self.assertEqual(
            result.invalid_by_type,
            {
                ValidationErrorCode.INVALID_EMAIL: 1,
                ValidationErrorCode.MISSING_CLIENT_COMPANY: 1,
            },
        )

    def test_empty_input_has_empty_aggregates(self) -> None:
        result = analyze_incidents([])

        self.assertEqual(result.total_records, 0)
        self.assertEqual(result.valid_records, 0)
        self.assertEqual(result.invalid_records, 0)
        self.assertIsNone(result.average_satisfaction)
        self.assertEqual(result.by_category, {})
        self.assertEqual(result.by_status, {})
        self.assertEqual(result.satisfaction_distribution, {})
        self.assertEqual(result.invalid_by_type, {})

    def test_dataset_matches_expected_unit_four_metrics(self) -> None:
        source = Path(__file__).parents[3] / "scripts" / "incidents-nexova.csv"
        result = analyze_incidents_csv(source)

        self.assertEqual(result.total_records, 100)
        self.assertEqual(result.valid_records, 96)
        self.assertEqual(result.invalid_records, 4)
        self.assertEqual(
            result.by_category,
            {
                IncidentCategory.TECHNICAL: 28,
                IncidentCategory.BILLING: 18,
                IncidentCategory.ACCESS: 21,
                IncidentCategory.HR_QUERY: 17,
                IncidentCategory.COMPLAINT: 12,
            },
        )
        self.assertEqual(
            result.by_status,
            {
                IncidentStatus.OPEN: 27,
                IncidentStatus.CLOSED: 56,
                IncidentStatus.DISCARDED: 13,
            },
        )
        self.assertEqual(result.satisfaction_distribution, {1: 2, 2: 5, 3: 10, 4: 22, 5: 17})
        self.assertEqual(result.average_satisfaction, 3.84)
        self.assertEqual(
            result.invalid_by_type,
            {
                ValidationErrorCode.MISSING_CLIENT_COMPANY: 1,
                ValidationErrorCode.INVALID_CATEGORY: 1,
                ValidationErrorCode.INVALID_EMAIL: 1,
                ValidationErrorCode.CLOSED_WITHOUT_SATISFACTION_SCORE: 1,
            },
        )
        self.assertNotIn("customer_email", result.__dataclass_fields__)
        self.assertNotIn("customer@example.com", repr(result))


if __name__ == "__main__":
    unittest.main()
