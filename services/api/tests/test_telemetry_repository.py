"""Unit tests for telemetry storage configuration and allowlisted tags."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.telemetry.repository import (
    TELEMETRY_DATABASE_URL_ENV,
    TelemetryStorageUnavailable,
    get_telemetry_database_url,
)
from app.telemetry.tags import filter_tags


class TelemetryConfigurationTests(unittest.TestCase):
    def test_requires_dedicated_postgresql_url(self) -> None:
        with patch.dict(os.environ, {TELEMETRY_DATABASE_URL_ENV: ""}, clear=False):
            with self.assertRaises(TelemetryStorageUnavailable):
                get_telemetry_database_url()

        with patch.dict(os.environ, {TELEMETRY_DATABASE_URL_ENV: "sqlite:///telemetry.db"}, clear=False):
            with self.assertRaises(TelemetryStorageUnavailable):
                get_telemetry_database_url()

    def test_accepts_private_postgresql_url_without_using_database_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite:///inventory.db",
                TELEMETRY_DATABASE_URL_ENV: "postgresql://user:password@db.example/telemetry",
            },
            clear=False,
        ):
            self.assertEqual(
                get_telemetry_database_url(),
                "postgresql://user:password@db.example/telemetry",
            )


class TelemetryTagTests(unittest.TestCase):
    def test_keeps_only_allowlisted_dimensions(self) -> None:
        tags = filter_tags(
            "incident_status_changed",
            {"incident_id": "INC-1", "branch": "valencia", "email": "excluded@example.com"},
        )
        self.assertEqual(tags, {"incident_id": "INC-1", "branch": "valencia"})

    def test_unknown_event_type_produces_empty_tags(self) -> None:
        self.assertEqual(filter_tags("unknown_event", {"anything": "value"}), {})


if __name__ == "__main__":
    unittest.main()
