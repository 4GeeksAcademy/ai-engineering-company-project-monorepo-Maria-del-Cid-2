"""Tests for validation shared by the Incident Manager API and seed."""

import unittest

from nexova_shared.incidents.validation import validate_incident_values


class SharedIncidentValidationTests(unittest.TestCase):
    def test_accepts_a_complete_incident_payload(self) -> None:
        issues = validate_incident_values(
            {
                "title": "A valid incident",
                "description": "A detailed description.",
                "category": "sla_breach",
                "status": "open",
                "origin": "branch",
                "branch": "remote",
            }
        )

        self.assertEqual(issues, ())

    def test_reports_invalid_fields_without_framework_dependencies(self) -> None:
        issues = validate_incident_values(
            {
                "title": "",
                "description": "",
                "category": "unknown",
                "status": "closed",
                "origin": "unknown",
                "branch": "headquarters",
            }
        )

        self.assertEqual(
            {issue.field for issue in issues},
            {"title", "description", "category", "status", "origin", "branch"},
        )


if __name__ == "__main__":
    unittest.main()
