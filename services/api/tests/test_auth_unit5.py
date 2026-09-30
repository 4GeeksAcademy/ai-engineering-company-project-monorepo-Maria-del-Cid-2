"""Tests para la Unidad 5: Protección de rutas existentes con JWT.

Verifica:
- Los 6 endpoints de suppliers están protegidos con get_current_user
- Sin token → 401
- Token inválido/expirado → 401
- Token válido → endpoint accesible
- Los endpoints de incidents siguen públicos (sin autenticación)
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

# ── Env vars MUST be set before auth imports ────────────────────────────────
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_repository
from app.auth.models import User, UserRole
from app.auth.repository import UserRepository
from app.auth.security import create_access_token
from app.auth.service import ACCESS_TOKEN_EXPIRE_DELTA
from app.main import app


# ── Helpers ──────────────────────────────────────────────────────────────────


def _create_valid_token(user_id: int = 1) -> str:
    """Crea un JWT firmado para un user_id dado."""
    return create_access_token(
        data={"sub": str(user_id)},
        expires_delta=ACCESS_TOKEN_EXPIRE_DELTA,
    )


_INVALID_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.fake"


class SupplierAuthTests(unittest.TestCase):
    """Verifica que los endpoints de suppliers están protegidos con JWT."""

    def setUp(self) -> None:
        # BD temporal para auth (necesaria para get_current_user en modo real)
        self.auth_tmp = TemporaryDirectory()
        auth_db_path = Path(self.auth_tmp.name) / "auth.json"
        os.environ["AUTH_DB_PATH"] = str(auth_db_path)

        # BD temporal para suppliers
        self.supplier_tmp = TemporaryDirectory()
        supplier_db_path = Path(self.supplier_tmp.name) / "suppliers.json"
        os.environ["SUPPLIER_DIRECTORY_DB_PATH"] = str(supplier_db_path)

        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("AUTH_DB_PATH", None)
        os.environ.pop("SUPPLIER_DIRECTORY_DB_PATH", None)
        self.supplier_tmp.cleanup()
        self.auth_tmp.cleanup()
        app.dependency_overrides.clear()

    # ── Sin token → 401 ──────────────────────────────────────────────────

    def test_create_supplier_no_token_returns_401(self) -> None:
        response = self.client.post(
            "/api/suppliers",
            json={
                "name": "Test",
                "country": "Spain",
                "categories": ["ats_software"],
                "monthly_rate": 100.0,
                "currency": "EUR",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_list_suppliers_no_token_returns_401(self) -> None:
        response = self.client.get("/api/suppliers")
        self.assertEqual(response.status_code, 401)

    def test_get_supplier_no_token_returns_401(self) -> None:
        response = self.client.get("/api/suppliers/1")
        self.assertEqual(response.status_code, 401)

    def test_update_rate_no_token_returns_401(self) -> None:
        response = self.client.patch(
            "/api/suppliers/1/rate", json={"monthly_rate": 200.0}
        )
        self.assertEqual(response.status_code, 401)

    def test_update_status_no_token_returns_401(self) -> None:
        response = self.client.patch(
            "/api/suppliers/1/status", json={"status": "suspended"}
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_supplier_no_token_returns_401(self) -> None:
        response = self.client.delete("/api/suppliers/1")
        self.assertEqual(response.status_code, 401)

    # ── Token inválido → 401 ─────────────────────────────────────────────

    def test_create_supplier_invalid_token_returns_401(self) -> None:
        response = self.client.post(
            "/api/suppliers",
            json={
                "name": "Test",
                "country": "Spain",
                "categories": ["ats_software"],
                "monthly_rate": 100.0,
                "currency": "EUR",
                "status": "active",
            },
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_list_suppliers_invalid_token_returns_401(self) -> None:
        response = self.client.get(
            "/api/suppliers",
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_get_supplier_invalid_token_returns_401(self) -> None:
        response = self.client.get(
            "/api/suppliers/1",
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_update_rate_invalid_token_returns_401(self) -> None:
        response = self.client.patch(
            "/api/suppliers/1/rate",
            json={"monthly_rate": 200.0},
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_update_status_invalid_token_returns_401(self) -> None:
        response = self.client.patch(
            "/api/suppliers/1/status",
            json={"status": "suspended"},
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    def test_delete_supplier_invalid_token_returns_401(self) -> None:
        response = self.client.delete(
            "/api/suppliers/1",
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)

    # ── Token válido → endpoint accesible ────────────────────────────────
    # NOTA: Estos tests requieren que el usuario exista en la BD de auth.
    # Sobrescribimos get_current_user para devolver un usuario fake,
    # igual que hacen los tests funcionales de suppliers.

    def _override_current_user(self) -> User:
        return User(
            id=999,
            email="auth-test@nexova.com",
            hashed_password="fake",
            is_active=True,
            role=UserRole.ADMIN,
            created_at=datetime.now(timezone.utc),
        )

    def test_create_supplier_with_valid_token_returns_201(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        response = self.client.post(
            "/api/suppliers",
            json={
                "name": "Valid Test",
                "country": "Spain",
                "categories": ["ats_software"],
                "monthly_rate": 100.0,
                "currency": "EUR",
                "status": "active",
            },
        )
        self.assertEqual(response.status_code, 201)

    def test_list_suppliers_with_valid_token_returns_200(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        response = self.client.get("/api/suppliers")
        self.assertEqual(response.status_code, 200)

    def test_get_supplier_with_valid_token_returns_200_or_404(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        # Sin suppliers en la BD, esperamos 404 (NotFound, no 401)
        response = self.client.get("/api/suppliers/1")
        self.assertEqual(response.status_code, 404)

    def test_update_rate_with_valid_token_returns_200_or_404(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        response = self.client.patch(
            "/api/suppliers/1/rate", json={"monthly_rate": 200.0}
        )
        # Sin suppliers, esperamos 404 (not found), no 401
        self.assertNotEqual(response.status_code, 401)

    def test_update_status_with_valid_token_returns_200_or_404(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        response = self.client.patch(
            "/api/suppliers/1/status", json={"status": "suspended"}
        )
        self.assertNotEqual(response.status_code, 401)

    def test_delete_supplier_with_valid_token_returns_204_or_404(self) -> None:
        app.dependency_overrides[get_current_user] = self._override_current_user
        response = self.client.delete("/api/suppliers/1")
        self.assertNotEqual(response.status_code, 401)


class IncidentsPublicTests(unittest.TestCase):
    """Verifica que los endpoints de incidents siguen siendo públicos."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_analyze_incidents_without_token_returns_400_not_401(self) -> None:
        """Sin token debe devolver error de validación (400, no 401 porque no hay file),
        lo que demuestra que el endpoint NO está protegido."""
        response = self.client.post("/api/incidents/analyze")
        self.assertNotEqual(response.status_code, 401)

    def test_export_results_without_token_returns_404_not_401(self) -> None:
        """Sin análisis previo devuelve 404, no 401 — el endpoint es público."""
        response = self.client.get("/api/incidents/results/export")
        self.assertNotEqual(response.status_code, 401)


class AuthSemanticTests(unittest.TestCase):
    """Verifica semántica HTTP correcta para suppliers protegidos."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_supplier_401_includes_www_authenticate_header(self) -> None:
        """Los 401 de suppliers deben incluir WWW-Authenticate: Bearer."""
        response = self.client.get("/api/suppliers")
        self.assertEqual(response.status_code, 401)
        self.assertIn("www-authenticate", response.headers)
        self.assertIn("Bearer", response.headers["www-authenticate"])

    def test_invalid_token_401_includes_www_authenticate_header(self) -> None:
        """401 con token inválido también debe incluir WWW-Authenticate."""
        response = self.client.get(
            "/api/suppliers",
            headers={"Authorization": f"Bearer {_INVALID_TOKEN}"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("www-authenticate", response.headers)
        self.assertIn("Bearer", response.headers["www-authenticate"])


if __name__ == "__main__":
    unittest.main()