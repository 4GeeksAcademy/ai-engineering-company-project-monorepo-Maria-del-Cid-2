"""Unit 1 tests for Incident Analysis domain contracts."""

import unittest

from app.incidents.constants import (
    IncidentCategory,
    IncidentStatus,
    ValidationErrorCode,
)
from app.incidents.models import IncidentAnalysisResult, IncidentRecord


class IncidentDomainModelsTests(unittest.TestCase):
    def test_incident_record_uses_domain_enums(self) -> None:
        record = IncidentRecord(
            category=IncidentCategory.TECHNICAL,
            status=IncidentStatus.CLOSED,
            satisfaction_score=4,
        )

        self.assertEqual(record.category, IncidentCategory.TECHNICAL)
        self.assertEqual(record.status, IncidentStatus.CLOSED)
        self.assertEqual(record.satisfaction_score, 4)

    def test_analysis_result_stores_aggregates_only(self) -> None:
        result = IncidentAnalysisResult(
            total_records=100,
            valid_records=96,
            invalid_records=4,
            by_category={IncidentCategory.TECHNICAL: 28},
            by_status={IncidentStatus.CLOSED: 56},
            satisfaction_distribution={4: 22},
            average_satisfaction=3.84,
            invalid_by_type={ValidationErrorCode.INVALID_EMAIL: 1},
        )

        self.assertEqual(result.total_records, 100)
        self.assertEqual(result.valid_records, 96)
        self.assertEqual(result.invalid_records, 4)
        self.assertNotIn("customer_email", result.__dataclass_fields__)
        self.assertNotIn("raw_rows", result.__dataclass_fields__)

    def test_empty_aggregate_mappings_are_available_by_default(self) -> None:
        result = IncidentAnalysisResult(
            total_records=0,
            valid_records=0,
            invalid_records=0,
        )

        self.assertEqual(result.by_category, {})
        self.assertEqual(result.by_status, {})
        self.assertEqual(result.satisfaction_distribution, {})
        self.assertEqual(result.invalid_by_type, {})
        self.assertIsNone(result.average_satisfaction)


if __name__ == "__main__":
    unittest.main()
