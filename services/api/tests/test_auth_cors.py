"""Tests for explicit CORS origins and profile preflight requests."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


def _get_cors_origins() -> list[str]:
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
    from app.main import get_cors_origins

    return get_cors_origins()


def _get_app():
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
    from app.main import app

    return app


class CorsConfigurationTests(unittest.TestCase):
    def test_cors_origins_are_trimmed_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": " https://nexova.example, http://localhost:3100 "},
        ):
            self.assertEqual(
                _get_cors_origins(),
                ["https://nexova.example", "http://localhost:3100"],
            )

    def test_cors_origins_reject_wildcard(self) -> None:
        with patch.dict(os.environ, {"CORS_ORIGINS": "*"}):
            with self.assertRaises(ValueError):
                _get_cors_origins()

    def test_profile_put_preflight_allows_authorized_origin(self) -> None:
        origins = _get_cors_origins()
        if not origins:
            self.skipTest("CORS_ORIGINS is empty")

        response = TestClient(_get_app()).options(
            "/api/profiles/me",
            headers={
                "Origin": origins[0],
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], origins[0])
        self.assertIn("PUT", response.headers["access-control-allow-methods"])
        allowed_headers = response.headers["access-control-allow-headers"].lower()
        self.assertIn("authorization", allowed_headers)
        self.assertIn("content-type", allowed_headers)

    def test_profile_put_preflight_rejects_unauthorized_origin(self) -> None:
        response = TestClient(_get_app()).options(
            "/api/profiles/me",
            headers={
                "Origin": "https://unauthorized.example.test",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)


if __name__ == "__main__":
    unittest.main()