"""Tests para la Unidad 3: Auth Service + get_current_user.

Verifica:
- AuthService.authenticate() con casos válidos e inválidos
- AuthService.create_token() genera tokens correctos
- get_current_user (dependencia FastAPI) con OpenAPI TestClient
- Cada error de autenticación produce HTTP 401, nunca 403
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

# ── Env vars MUST be set before auth imports ────────────────────────────────
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-3")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from jose import jwt
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.auth.database import create_database
from app.auth.models import User, UserCreate, UserRole
from app.auth.repository import UserRepository
from app.auth.security import create_access_token, hash_password, decode_access_token
from app.auth.service import AuthService, AuthenticationError
from app.auth.dependencies import get_current_user, get_repository


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_user(
    repo: UserRepository,
    email: str = "active@example.com",
    password: str = "validpass123",
    is_active: bool = True,
) -> User:
    """Crea un usuario en el repositorio con datos controlados."""
    hashed = hash_password(password)
    user = repo.create(UserCreate(email=email, password=password), hashed)
    if not is_active:
        repo._table.update({"is_active": False}, doc_ids=[user.id])
    return repo.get(user.id)  # type: ignore[return-value]


def _make_test_app(repo: UserRepository) -> FastAPI:
    """Crea una app de prueba que sobreescribe el repositorio de auth.

    Así get_current_user consulta la BD temporal en lugar de la BD real.
    """
    app = FastAPI()

    def _override_repo() -> UserRepository:
        return repo

    app.dependency_overrides[get_repository] = _override_repo

    @app.get("/me")
    def _read_me(user: User = Depends(get_current_user)) -> User:
        return user

    return app


# ══════════════════════════════════════════════════════════════════════════════
# AuthService — unit tests (sin FastAPI)
# ══════════════════════════════════════════════════════════════════════════════


class AuthServiceTests(unittest.TestCase):
    """Tests de AuthService con TinyDB temporal."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.service = AuthService(self.repo)
        self.active_user = _make_user(self.repo, "active@example.com", "validpass123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    # ── authenticate ────────────────────────────────────────────────────

    def test_authenticate_valid_credentials(self) -> None:
        """Usuario existente + password correcta → autenticación válida."""
        user = self.service.authenticate("active@example.com", "validpass123")
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "active@example.com")
        self.assertTrue(user.is_active)

    def test_authenticate_invalid_email(self) -> None:
        """Email inexistente → AuthenticationError."""
        with self.assertRaises(AuthenticationError):
            self.service.authenticate("noone@example.com", "anypass")

    def test_authenticate_wrong_password(self) -> None:
        """Password incorrecta → AuthenticationError."""
        with self.assertRaises(AuthenticationError):
            self.service.authenticate("active@example.com", "wrongpassword")

    def test_authenticate_inactive_user(self) -> None:
        """Usuario inactivo → AuthenticationError."""
        _make_user(self.repo, "inactive@example.com", "pass123", is_active=False)
        with self.assertRaises(AuthenticationError):
            self.service.authenticate("inactive@example.com", "pass123")

    def test_authenticate_error_message_is_generic(self) -> None:
        """El mensaje de error no revela qué campo falló."""
        messages: list[str] = []
        for scenario in [
            ("noone@example.com", "x"),       # email inexistente
            ("active@example.com", "x"),       # password incorrecta
        ]:
            with self.subTest(email=scenario[0]):
                try:
                    self.service.authenticate(*scenario)
                except AuthenticationError as e:
                    messages.append(str(e))
        # También usuario inactivo
        _make_user(self.repo, "blocked@example.com", "x", is_active=False)
        try:
            self.service.authenticate("blocked@example.com", "x")
        except AuthenticationError as e:
            messages.append(str(e))
        for msg in messages:
            self.assertEqual(msg, "Invalid credentials")

    # ── create_token ────────────────────────────────────────────────────

    def test_create_token_contains_user_id_in_sub(self) -> None:
        """El token generado contiene el user id en el campo 'sub'."""
        token = self.service.create_token(self.active_user)
        payload = decode_access_token(token)
        self.assertIn("sub", payload)
        self.assertEqual(int(payload["sub"]), self.active_user.id)

    def test_create_token_contains_expiration(self) -> None:
        """El token generado contiene 'exp' (timestamp futuro)."""
        token = self.service.create_token(self.active_user)
        payload = decode_access_token(token)
        self.assertIn("exp", payload)
        exp = payload["exp"]
        now = datetime.now(timezone.utc).timestamp()
        self.assertGreater(exp, now)

    def test_create_token_does_not_contain_email_as_primary_id(self) -> None:
        """El identificador principal es 'sub' (user id), no 'email'."""
        token = self.service.create_token(self.active_user)
        payload = decode_access_token(token)
        self.assertEqual(payload.get("sub"), str(self.active_user.id))
        self.assertNotIn("email", payload)


# ══════════════════════════════════════════════════════════════════════════════
# get_current_user — tests con TestClient
# ══════════════════════════════════════════════════════════════════════════════


class GetCurrentUserTests(unittest.TestCase):
    """Tests de la dependencia get_current_user via TestClient."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "auth_get_current_user.json"
        cls.database = create_database(cls.db_path)
        cls.repo = UserRepository(cls.database)
        cls.service = AuthService(cls.repo)
        cls.active_user = _make_user(cls.repo, "alice@example.com", "secret123")
        cls.inactive_user = _make_user(
            cls.repo, "bob@example.com", "secret123", is_active=False
        )
        cls.valid_token = cls.service.create_token(cls.active_user)
        cls.client = TestClient(_make_test_app(cls.repo))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.database.close()
        cls.temp_dir.cleanup()

    def _auth_header(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    # ── Token válido ────────────────────────────────────────────────────

    def test_valid_token_returns_user(self) -> None:
        """Token válido → devuelve User."""
        response = self.client.get("/me", headers=self._auth_header(self.valid_token))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "alice@example.com")
        self.assertTrue(data["is_active"])

    # ── Usuario inexistente ─────────────────────────────────────────────

    def test_token_for_nonexistent_user_returns_401(self) -> None:
        """Token con sub válido pero usuario inexistente → 401."""
        token = create_access_token(data={"sub": "99999"})
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── Token expirado ──────────────────────────────────────────────────

    def test_expired_token_returns_401(self) -> None:
        """Token expirado → 401."""
        token = create_access_token(
            data={"sub": str(self.active_user.id)},
            expires_delta=timedelta(hours=-1),
        )
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── Firma inválida ──────────────────────────────────────────────────

    def test_invalid_signature_returns_401(self) -> None:
        """Token con firma inválida → 401."""
        token = jwt.encode(
            {
                "sub": str(self.active_user.id),
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "different-secret-key",
            algorithm="HS256",
        )
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── Token malformado ────────────────────────────────────────────────

    def test_malformed_token_returns_401(self) -> None:
        """Token que no es un JWT válido → 401."""
        response = self.client.get("/me", headers=self._auth_header("not-a-jwt-token"))
        self.assertEqual(response.status_code, 401)

    # ── Token sin sub ───────────────────────────────────────────────────

    def test_token_without_sub_returns_401(self) -> None:
        """Token JWT válido pero sin claim 'sub' → 401."""
        token = create_access_token(data={"some": "data"})
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── sub inválido ────────────────────────────────────────────────────

    def test_token_with_invalid_sub_returns_401(self) -> None:
        """Token con 'sub' no convertible a int → 401."""
        token = create_access_token(data={"sub": "not-an-integer"})
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── Usuario inactivo ────────────────────────────────────────────────

    def test_inactive_user_token_returns_401(self) -> None:
        """Token válido pero usuario inactivo → 401."""
        token = self.service.create_token(self.inactive_user)
        response = self.client.get("/me", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 401)

    # ── Token ausente ───────────────────────────────────────────────────

    def test_missing_token_returns_401(self) -> None:
        """Request sin Authorization header → 401 (OAuth2)."""
        response = self.client.get("/me")
        self.assertEqual(response.status_code, 401)

    # ── WWW-Authenticate header ─────────────────────────────────────────

    def test_401_includes_www_authenticate_bearer(self) -> None:
        """Las respuestas 401 incluyen WWW-Authenticate: Bearer."""
        response = self.client.get("/me", headers=self._auth_header("garbage"))
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)
        self.assertIn("Bearer", response.headers["WWW-Authenticate"])


# ══════════════════════════════════════════════════════════════════════════════
# HTTP semantics — 401 vs 403
# ══════════════════════════════════════════════════════════════════════════════


class AuthHttpSemanticTests(unittest.TestCase):
    """Comprueba que todos los errores de autenticación son 401, no 403."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = TemporaryDirectory()
        cls.db_path = Path(cls.temp_dir.name) / "auth_semantic.json"
        cls.database = create_database(cls.db_path)
        cls.repo = UserRepository(cls.database)
        cls.service = AuthService(cls.repo)
        cls.active_user = _make_user(cls.repo, "carol@example.com", "pass123")
        cls.inactive_user = _make_user(
            cls.repo, "dave@example.com", "pass123", is_active=False
        )
        cls.client = TestClient(_make_test_app(cls.repo))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.database.close()
        cls.temp_dir.cleanup()

    def _auth_header(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_all_auth_errors_are_401_not_403(self) -> None:
        """Verifica que ningún error de autenticación devuelve 403."""
        scenarios: list[tuple[str, object]] = [
            (
                "missing token",
                self.client.get("/me"),
            ),
            (
                "invalid signature",
                self.client.get(
                    "/me",
                    headers=self._auth_header(
                        jwt.encode(
                            {
                                "sub": "1",
                                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                            },
                            "wrong-key",
                            algorithm="HS256",
                        )
                    ),
                ),
            ),
            (
                "malformed",
                self.client.get("/me", headers=self._auth_header("not-a-token")),
            ),
            (
                "expired",
                self.client.get(
                    "/me",
                    headers=self._auth_header(
                        create_access_token(
                            data={"sub": str(self.active_user.id)},
                            expires_delta=timedelta(hours=-1),
                        )
                    ),
                ),
            ),
            (
                "inactive user",
                self.client.get(
                    "/me",
                    headers=self._auth_header(self.service.create_token(self.inactive_user)),
                ),
            ),
        ]
        for name, response in scenarios:
            with self.subTest(scenario=name):
                self.assertEqual(
                    response.status_code,
                    401,
                    f"Escenario '{name}' debería ser 401, no {response.status_code}",
                )
                self.assertNotEqual(
                    response.status_code,
                    403,
                    f"Escenario '{name}' no debe devolver 403",
                )


if __name__ == "__main__":
    unittest.main()