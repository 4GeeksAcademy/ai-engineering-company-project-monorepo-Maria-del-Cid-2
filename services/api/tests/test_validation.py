"""Tests for the Unit 3 incident validator."""

import unittest

from app.incidents.constants import ValidationErrorCode
from app.incidents.csv_reader import NormalizedIncidentRow
from app.incidents.validation import validate_incident


class IncidentValidationTests(unittest.TestCase):
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

    def assert_error(self, row: NormalizedIncidentRow, code: ValidationErrorCode) -> None:
        result = validate_incident(row)
        self.assertFalse(result.is_valid)
        self.assertIn(code, result.errors)
        self.assertIsNone(result.record)

    def test_valid_row_returns_domain_record(self) -> None:
        result = validate_incident(self.make_row())

        self.assertTrue(result.is_valid)
        self.assertEqual(result.errors, ())
        self.assertIsNotNone(result.record)
        self.assertEqual(result.record.category.value, "ACCESS")
        self.assertEqual(result.record.status.value, "CLOSED")
        self.assertEqual(result.record.satisfaction_score, 4)

    def test_missing_client_company(self) -> None:
        self.assert_error(
            self.make_row(client_company=" "),
            ValidationErrorCode.MISSING_CLIENT_COMPANY,
        )

    def test_missing_or_invalid_category(self) -> None:
        self.assert_error(
            self.make_row(category="UNKNOWN"),
            ValidationErrorCode.INVALID_CATEGORY,
        )

    def test_empty_or_short_description(self) -> None:
        self.assert_error(
            self.make_row(description="abcd"),
            ValidationErrorCode.INVALID_DESCRIPTION,
        )

    def test_missing_or_invalid_agent_id(self) -> None:
        self.assert_error(
            self.make_row(agent_id="AGT-7"),
            ValidationErrorCode.INVALID_AGENT_ID,
        )

    def test_missing_or_invalid_email(self) -> None:
        self.assert_error(
            self.make_row(customer_email="invalid-email"),
            ValidationErrorCode.INVALID_EMAIL,
        )

    def test_closed_without_satisfaction_score(self) -> None:
        self.assert_error(
            self.make_row(satisfaction_score=None),
            ValidationErrorCode.CLOSED_WITHOUT_SATISFACTION_SCORE,
        )

    def test_score_out_of_range(self) -> None:
        self.assert_error(
            self.make_row(satisfaction_score=6),
            ValidationErrorCode.SATISFACTION_SCORE_OUT_OF_RANGE,
        )

    def test_non_numeric_score_is_out_of_range(self) -> None:
        self.assert_error(
            self.make_row(satisfaction_score="not-a-number"),
            ValidationErrorCode.SATISFACTION_SCORE_OUT_OF_RANGE,
        )

    def test_multiple_rules_are_reported_together(self) -> None:
        result = validate_incident(
            self.make_row(
                client_company="",
                category="",
                description="bad",
                agent_id="wrong",
                customer_email="no-email",
                satisfaction_score=9,
            )
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(
            set(result.errors),
            {
                ValidationErrorCode.MISSING_CLIENT_COMPANY,
                ValidationErrorCode.INVALID_CATEGORY,
                ValidationErrorCode.INVALID_DESCRIPTION,
                ValidationErrorCode.INVALID_AGENT_ID,
                ValidationErrorCode.INVALID_EMAIL,
                ValidationErrorCode.SATISFACTION_SCORE_OUT_OF_RANGE,
            },
        )

    def test_validation_result_never_exposes_source_row_or_email(self) -> None:
        row = self.make_row(customer_email="private.customer@example.com", category="BAD")
        result = validate_incident(row)

        self.assertNotIn("private.customer@example.com", repr(result))
        self.assertNotIn("customer_email", result.__dataclass_fields__)
        self.assertNotIn("private.customer@example.com", str(result.errors))


if __name__ == "__main__":
    unittest.main()
