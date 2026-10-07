"""Tests para la Unidad 4: Auth + Users + Profiles HTTP API.

Verifica:
- Auth: login (credenciales válidas, inválidas, inactivo)
- Auth: /me (con/sin profile, sin token, token inválido)
- Users: CRUD con autorización (self, admin, manager)
- Profiles: /me (GET y PUT)
- 401 vs 403 correctamente diferenciados
- hashed_password nunca en respuestas
- Compensación en creación User + Profile
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from tempfile import TemporaryDirectory

# ── Env vars MUST be set before auth imports ────────────────────────────────
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.database import create_database
from app.auth.dependencies import get_current_user, get_profile_repository, get_repository
from app.auth.models import ProfileCreate, User, UserCreate, UserRole
from app.auth.repository import (
    DuplicateEmailError,
    ProfileRepository,
    UserRepository,
)
from app.auth.routers.auth_router import router as auth_router
from app.auth.routers.profiles_router import router as profiles_router
from app.auth.routers.users_router import router as users_router
from app.auth.schemas import UserCreateRequest
from app.auth.security import hash_password
from app.auth.service import AuthService


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_test_app(
    repo: UserRepository,
    profile_repo: ProfileRepository | None = None,
) -> FastAPI:
    """Crea una app de prueba con repositorios sobrescritos."""
    app = FastAPI()

    def _override_repo() -> UserRepository:
        return repo

    if profile_repo is not None:
        pr = profile_repo

        def _override_profile_repo() -> ProfileRepository:
            return pr

        app.dependency_overrides[get_profile_repository] = _override_profile_repo

    app.dependency_overrides[get_repository] = _override_repo
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(profiles_router)
    return app


def _create_test_user(
    repo: UserRepository,
    email: str = "test@example.com",
    password: str = "testpass123",
    role: UserRole = UserRole.USER,
    is_active: bool = True,
) -> User:
    """Crea un usuario en el repositorio y devuelve el User persistido."""
    hashed = hash_password(password)
    create_payload = UserCreate(email=email, password=password)
    return repo.create_with_attrs(create_payload, hashed, is_active=is_active, role=role)


def _login(client: TestClient, email: str, password: str) -> str:
    """Helper: hace login y devuelve el access_token."""
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════════════════════
# Auth: Login
# ══════════════════════════════════════════════════════════════════════════════


class AuthLoginTests(unittest.TestCase):
    """Tests del endpoint POST /api/auth/login."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_login.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.service = AuthService(self.repo)
        self.app = _make_test_app(self.repo)
        self.client = TestClient(self.app)
        self.active_user = _create_test_user(self.repo, "alice@example.com", "secret123")
        self.admin_user = _create_test_user(
            self.repo, "admin@example.com", "admin123", role=UserRole.ADMIN
        )
        self.inactive_user = _create_test_user(
            self.repo, "bob@example.com", "secret123", is_active=False
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_login_valid_credentials_returns_token(self) -> None:
        """Login correcto → 200 con access_token."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIsInstance(data["access_token"], str)
        self.assertGreater(len(data["access_token"]), 0)

    def test_login_returns_token_type_bearer(self) -> None:
        """Login correcto → token_type=bearer."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "secret123"},
        )
        data = response.json()
        self.assertEqual(data["token_type"], "bearer")

    def test_login_wrong_password_returns_401(self) -> None:
        """Password incorrecta → 401."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "wrongpass"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_nonexistent_email_returns_401(self) -> None:
        """Email inexistente → 401."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "noone@example.com", "password": "anypass"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_inactive_user_returns_401(self) -> None:
        """Usuario inactivo → 401."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "bob@example.com", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_does_not_require_bearer(self) -> None:
        """Login es público, no requiere Bearer token."""
        response = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "secret123"},
            headers={},  # Sin Authorization
        )
        self.assertEqual(response.status_code, 200)

    def test_login_is_oauth2_compatible(self) -> None:
        """Login acepta OAuth2PasswordRequestForm (username/password)."""
        # OAuth2PasswordRequestForm usa 'username' como campo, no 'email'
        response = self.client.post(
            "/api/auth/login",
            data={"username": "alice@example.com", "password": "secret123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())


# ══════════════════════════════════════════════════════════════════════════════
# Auth: Me
# ══════════════════════════════════════════════════════════════════════════════


class AuthMeTests(unittest.TestCase):
    """Tests del endpoint GET /api/auth/me."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_me.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.service = AuthService(self.repo)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "carol@example.com", "pass123")
        self.token = _login(self.client, "carol@example.com", "pass123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_me_with_valid_token_returns_200(self) -> None:
        """Token válido → 200."""
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        self.assertEqual(response.status_code, 200)

    def test_me_returns_email(self) -> None:
        """/me devuelve email del usuario."""
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertEqual(data["email"], "carol@example.com")

    def test_me_returns_role(self) -> None:
        """/me devuelve role del usuario."""
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertEqual(data["role"], "user")

    def test_me_returns_profile_as_none_when_no_profile(self) -> None:
        """/me devuelve profile=None si no existe."""
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertIsNone(data["profile"])

    def test_me_returns_profile_when_exists(self) -> None:
        """/me devuelve profile si existe."""
        self.profile_repo.create(
            self.user.id,
            ProfileCreate(name="Carol", phone="+123", address="Main St"),
        )
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertIsNotNone(data["profile"])
        self.assertEqual(data["profile"]["name"], "Carol")
        self.assertEqual(data["profile"]["phone"], "+123")
        self.assertEqual(data["profile"]["address"], "Main St")

    def test_me_never_returns_hashed_password(self) -> None:
        """/me nunca devuelve hashed_password."""
        response = self.client.get("/api/auth/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertNotIn("hashed_password", data)

    def test_me_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)

    def test_me_with_invalid_token_returns_401(self) -> None:
        """Token inválido → 401."""
        response = self.client.get("/api/auth/me", headers=_auth_header("garbage-token"))
        self.assertEqual(response.status_code, 401)


# ══════════════════════════════════════════════════════════════════════════════
# Users: POST /api/users
# ══════════════════════════════════════════════════════════════════════════════


class CreateUserTests(unittest.TestCase):
    """Tests del endpoint POST /api/users (público)."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_create_user.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_create_user_without_auth(self) -> None:
        """Crear usuario no requiere autenticación."""
        response = self.client.post(
            "/api/users",
            json={"email": "new@example.com", "password": "pass123"},
        )
        self.assertEqual(response.status_code, 201)

    def test_create_user_password_is_hashed(self) -> None:
        """El password se almacena hasheado, no en texto plano."""
        response = self.client.post(
            "/api/users",
            json={"email": "new@example.com", "password": "pass123"},
        )
        self.assertEqual(response.status_code, 201)
        user = self.repo.get_by_email("new@example.com")
        self.assertIsNotNone(user)
        self.assertNotEqual(user.hashed_password, "pass123")
        self.assertTrue(user.hashed_password.startswith("$2b$"))  # bcrypt

    def test_create_user_response_no_hashed_password(self) -> None:
        """Respuesta de creación no incluye hashed_password."""
        response = self.client.post(
            "/api/users",
            json={"email": "new@example.com", "password": "pass123"},
        )
        data = response.json()
        self.assertNotIn("hashed_password", data)
        self.assertNotIn("password", data)

    def test_create_user_default_role_is_user(self) -> None:
        """Rol por defecto es 'user'."""
        response = self.client.post(
            "/api/users",
            json={"email": "new@example.com", "password": "pass123"},
        )
        data = response.json()
        self.assertEqual(data["role"], "user")

    def test_public_registration_rejects_role_and_active_overrides(self) -> None:
        """El registro público no permite elevar privilegios ni desactivar usuarios."""
        payloads = [
            {"email": "admin@example.com", "password": "pass123", "role": "admin"},
            {"email": "inactive@example.com", "password": "pass123", "is_active": False},
        ]

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post("/api/users", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertIsNone(self.repo.get_by_email(payload["email"]))

    def test_duplicate_registration_returns_409_without_creating_user(self) -> None:
        first = self.client.post(
            "/api/users",
            json={"email": "duplicate@example.com", "password": "first-pass"},
        )
        self.assertEqual(first.status_code, 201)
        user_count = len(self.repo.list())

        duplicate = self.client.post(
            "/api/users",
            json={"email": "duplicate@example.com", "password": "second-pass"},
        )

        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(len(self.repo.list()), user_count)

    def test_concurrent_duplicate_registration_is_serialized_in_one_process(self) -> None:
        barrier = Barrier(2)

        def register() -> bool:
            payload = UserCreate(email="race@example.com", password="pass123")
            hashed = hash_password("pass123")
            barrier.wait()
            try:
                self.repo.create_if_email_available(payload, hashed)
                return True
            except DuplicateEmailError:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            created = list(executor.map(lambda _: register(), range(2)))

        self.assertEqual(created.count(True), 1)
        self.assertEqual(len(self.repo.list()), 1)

    def test_create_user_with_profile(self) -> None:
        """Crear usuario con Profile opcional."""
        response = self.client.post(
            "/api/users",
            json={
                "email": "withprofile@example.com",
                "password": "pass123",
                "profile": {"name": "John", "phone": "+999", "address": "Earth"},
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["email"], "withprofile@example.com")
        # Verificar que el Profile se creó
        user = self.repo.get_by_email("withprofile@example.com")
        assert user is not None
        profile = self.profile_repo.get_by_user_id(user.id)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "John")
        self.assertEqual(profile.phone, "+999")

    def test_create_user_without_profile_works(self) -> None:
        """Crear usuario sin Profile funciona."""
        response = self.client.post(
            "/api/users",
            json={"email": "noprofile@example.com", "password": "pass123"},
        )
        self.assertEqual(response.status_code, 201)
        user = self.repo.get_by_email("noprofile@example.com")
        assert user is not None
        profile = self.profile_repo.get_by_user_id(user.id)
        self.assertIsNone(profile)


# ══════════════════════════════════════════════════════════════════════════════
# Users: GET /api/users
# ══════════════════════════════════════════════════════════════════════════════


class ListUsersTests(unittest.TestCase):
    """Tests del endpoint GET /api/users."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_list.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.service = AuthService(self.repo)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "listuser@example.com", "pass123")
        self.token = _login(self.client, "listuser@example.com", "pass123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_list_users_authenticated_returns_200(self) -> None:
        """Autenticado → 200."""
        response = self.client.get("/api/users", headers=_auth_header(self.token))
        self.assertEqual(response.status_code, 200)

    def test_list_users_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 401)

    def test_list_users_no_hashed_password(self) -> None:
        """Ningún elemento contiene hashed_password."""
        response = self.client.get("/api/users", headers=_auth_header(self.token))
        data = response.json()
        self.assertIsInstance(data, list)
        for user in data:
            self.assertNotIn("hashed_password", user)
            self.assertNotIn("password", user)

    def test_list_users_returns_correct_fields(self) -> None:
        """Lista devuelve campos esperados."""
        response = self.client.get("/api/users", headers=_auth_header(self.token))
        data = response.json()
        self.assertIsInstance(data, list)
        if data:
            user = data[0]
            self.assertIn("id", user)
            self.assertIn("email", user)
            self.assertIn("is_active", user)
            self.assertIn("role", user)
            self.assertIn("created_at", user)


# ══════════════════════════════════════════════════════════════════════════════
# Users: GET /api/users/{id}
# ══════════════════════════════════════════════════════════════════════════════


class GetUserTests(unittest.TestCase):
    """Tests del endpoint GET /api/users/{id}."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_getuser.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "normal@example.com", "pass123")
        self.admin = _create_test_user(
            self.repo, "admin@example.com", "admin123", role=UserRole.ADMIN
        )
        self.manager = _create_test_user(
            self.repo, "manager@example.com", "manager123", role=UserRole.MANAGER
        )
        self.other_user = _create_test_user(
            self.repo, "other@example.com", "other123"
        )
        self.user_token = _login(self.client, "normal@example.com", "pass123")
        self.admin_token = _login(self.client, "admin@example.com", "admin123")
        self.manager_token = _login(self.client, "manager@example.com", "manager123")
        self.other_token = _login(self.client, "other@example.com", "other123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_self_can_get_own_user(self) -> None:
        """Self → 200."""
        response = self.client.get(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "normal@example.com")

    def test_admin_can_get_any_user(self) -> None:
        """Admin → puede consultar otro usuario."""
        response = self.client.get(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.admin_token),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "other@example.com")

    def test_user_cannot_get_another_user(self) -> None:
        """User consultando otro → 403."""
        response = self.client.get(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.user_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_get_another_user(self) -> None:
        """Manager consultando otro → 403."""
        response = self.client.get(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.manager_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_get_nonexistent_user_returns_404(self) -> None:
        """Usuario inexistente → 404."""
        response = self.client.get(
            "/api/users/99999",
            headers=_auth_header(self.admin_token),
        )
        self.assertEqual(response.status_code, 404)

    def test_get_user_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.get(f"/api/users/{self.user.id}")
        self.assertEqual(response.status_code, 401)

    def test_get_user_no_hashed_password(self) -> None:
        """Respuesta no contiene hashed_password."""
        response = self.client.get(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
        )
        data = response.json()
        self.assertNotIn("hashed_password", data)


# ══════════════════════════════════════════════════════════════════════════════
# Users: PUT /api/users/{id}
# ══════════════════════════════════════════════════════════════════════════════


class UpdateUserTests(unittest.TestCase):
    """Tests del endpoint PUT /api/users/{id}."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_update.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "normal@example.com", "pass123")
        self.admin = _create_test_user(
            self.repo, "admin@example.com", "admin123", role=UserRole.ADMIN
        )
        self.manager = _create_test_user(
            self.repo, "manager@example.com", "manager123", role=UserRole.MANAGER
        )
        self.other_user = _create_test_user(
            self.repo, "other@example.com", "other123"
        )
        self.user_token = _login(self.client, "normal@example.com", "pass123")
        self.admin_token = _login(self.client, "admin@example.com", "admin123")
        self.manager_token = _login(self.client, "manager@example.com", "manager123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_self_can_update_own_email(self) -> None:
        """Self puede modificar su email."""
        response = self.client.put(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
            json={"email": "newemail@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "newemail@example.com")

    def test_admin_can_update_another_user(self) -> None:
        """Admin puede modificar otro usuario."""
        response = self.client.put(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.admin_token),
            json={"email": "updated@example.com"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "updated@example.com")

    def test_user_cannot_update_another_user(self) -> None:
        """User no puede modificar otro → 403."""
        response = self.client.put(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.user_token),
            json={"email": "hacked@example.com"},
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_update_another_user(self) -> None:
        """Manager no puede modificar arbitrariamente otro → 403."""
        response = self.client.put(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.manager_token),
            json={"email": "hacked@example.com"},
        )
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_change_own_role(self) -> None:
        """User no puede cambiarse su role → 403."""
        response = self.client.put(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
            json={"role": "admin"},
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_change_role(self) -> None:
        """Manager no puede cambiar role → 403."""
        response = self.client.put(
            f"/api/users/{self.manager.id}",
            headers=_auth_header(self.manager_token),
            json={"role": "admin"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_change_role(self) -> None:
        """Admin puede cambiar role."""
        response = self.client.put(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.admin_token),
            json={"role": "manager"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["role"], "manager")

    def test_update_nonexistent_user_returns_404(self) -> None:
        """Usuario inexistente → 404."""
        response = self.client.put(
            "/api/users/99999",
            headers=_auth_header(self.admin_token),
            json={"email": "noone@example.com"},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_response_no_hashed_password(self) -> None:
        """Respuesta no contiene hashed_password."""
        response = self.client.put(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
            json={"email": "clean@example.com"},
        )
        data = response.json()
        self.assertNotIn("hashed_password", data)


# ══════════════════════════════════════════════════════════════════════════════
# Users: DELETE /api/users/{id}
# ══════════════════════════════════════════════════════════════════════════════


class DeleteUserTests(unittest.TestCase):
    """Tests del endpoint DELETE /api/users/{id}."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_delete.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "normal@example.com", "pass123")
        self.admin = _create_test_user(
            self.repo, "admin@example.com", "admin123", role=UserRole.ADMIN
        )
        self.manager = _create_test_user(
            self.repo, "manager@example.com", "manager123", role=UserRole.MANAGER
        )
        self.other_user = _create_test_user(
            self.repo, "other@example.com", "other123"
        )
        self.user_with_profile = _create_test_user(
            self.repo, "withprofile@example.com", "pass123"
        )
        # Crear Profile para el usuario con profile
        self.profile_repo.create(
            self.user_with_profile.id,
            ProfileCreate(name="ToDelete", phone="+000", address="Nowhere"),
        )
        self.user_token = _login(self.client, "normal@example.com", "pass123")
        self.admin_token = _login(self.client, "admin@example.com", "admin123")
        self.manager_token = _login(self.client, "manager@example.com", "manager123")
        self.other_token = _login(self.client, "other@example.com", "other123")
        self.profile_token = _login(self.client, "withprofile@example.com", "pass123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_self_can_delete_self(self) -> None:
        """Self puede eliminarse."""
        response = self.client.delete(
            f"/api/users/{self.user.id}",
            headers=_auth_header(self.user_token),
        )
        self.assertEqual(response.status_code, 204)

    def test_admin_can_delete_other_user(self) -> None:
        """Admin puede eliminar otro usuario."""
        response = self.client.delete(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.admin_token),
        )
        self.assertEqual(response.status_code, 204)

    def test_user_cannot_delete_another_user(self) -> None:
        """User no puede eliminar otro → 403."""
        response = self.client.delete(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.user_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_cannot_delete_another_user(self) -> None:
        """Manager no puede eliminar otro → 403."""
        response = self.client.delete(
            f"/api/users/{self.other_user.id}",
            headers=_auth_header(self.manager_token),
        )
        self.assertEqual(response.status_code, 403)

    def test_delete_nonexistent_user_returns_404(self) -> None:
        """Usuario inexistente → 404."""
        response = self.client.delete(
            "/api/users/99999",
            headers=_auth_header(self.admin_token),
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_user_also_deletes_profile(self) -> None:
        """Eliminar User también elimina su Profile."""
        user_id = self.user_with_profile.id
        # Verificar que el Profile existe antes
        self.assertIsNotNone(self.profile_repo.get_by_user_id(user_id))
        response = self.client.delete(
            f"/api/users/{user_id}",
            headers=_auth_header(self.admin_token),
        )
        self.assertEqual(response.status_code, 204)
        # Verificar que el Profile también se eliminó
        self.assertIsNone(self.profile_repo.get_by_user_id(user_id))

    def test_delete_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.delete(f"/api/users/{self.user.id}")
        self.assertEqual(response.status_code, 401)


# ══════════════════════════════════════════════════════════════════════════════
# Profiles: GET /api/profiles/me
# ══════════════════════════════════════════════════════════════════════════════


class GetProfileMeTests(unittest.TestCase):
    """Tests del endpoint GET /api/profiles/me."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_profile_me.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "dave@example.com", "pass123")
        self.profile_repo.create(
            self.user.id,
            ProfileCreate(name="Dave", phone="+111", address="Here"),
        )
        self.token = _login(self.client, "dave@example.com", "pass123")
        self.user_no_profile = _create_test_user(
            self.repo, "noprofile@example.com", "pass456"
        )
        self.token_no_profile = _login(self.client, "noprofile@example.com", "pass456")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_get_profile_me_authenticated_with_profile(self) -> None:
        """Autenticado con Profile → 200."""
        response = self.client.get("/api/profiles/me", headers=_auth_header(self.token))
        self.assertEqual(response.status_code, 200)

    def test_get_profile_me_returns_correct_data(self) -> None:
        """Devuelve datos del Profile."""
        response = self.client.get("/api/profiles/me", headers=_auth_header(self.token))
        data = response.json()
        self.assertEqual(data["name"], "Dave")
        self.assertEqual(data["phone"], "+111")
        self.assertEqual(data["address"], "Here")
        self.assertEqual(data["user_id"], self.user.id)

    def test_get_profile_me_without_profile_returns_404(self) -> None:
        """Sin Profile → 404."""
        response = self.client.get(
            "/api/profiles/me", headers=_auth_header(self.token_no_profile)
        )
        self.assertEqual(response.status_code, 404)

    def test_get_profile_me_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.get("/api/profiles/me")
        self.assertEqual(response.status_code, 401)


# ══════════════════════════════════════════════════════════════════════════════
# Profiles: PUT /api/profiles/me
# ══════════════════════════════════════════════════════════════════════════════


class UpdateProfileMeTests(unittest.TestCase):
    """Tests del endpoint PUT /api/profiles/me."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_profile_update.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "eve@example.com", "pass123")
        self.profile_repo.create(
            self.user.id,
            ProfileCreate(name="Eve", phone="+222", address="There"),
        )
        self.token = _login(self.client, "eve@example.com", "pass123")
        self.user_no_profile = _create_test_user(
            self.repo, "noprofile2@example.com", "pass456"
        )
        self.token_no_profile = _login(
            self.client, "noprofile2@example.com", "pass456"
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_update_profile_name(self) -> None:
        """Actualiza name."""
        response = self.client.put(
            "/api/profiles/me",
            headers=_auth_header(self.token),
            json={"name": "Eve Updated"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Eve Updated")

    def test_update_profile_phone(self) -> None:
        """Actualiza phone."""
        response = self.client.put(
            "/api/profiles/me",
            headers=_auth_header(self.token),
            json={"phone": "+333"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["phone"], "+333")

    def test_update_profile_address(self) -> None:
        """Actualiza address."""
        response = self.client.put(
            "/api/profiles/me",
            headers=_auth_header(self.token),
            json={"address": "Nowhere"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["address"], "Nowhere")

    def test_update_profile_prevents_user_id_change(self) -> None:
        """No permite cambiar user_id (se ignora o rechaza)."""
        # ProfileUpdate tiene extra="forbid", así que user_id no está en el modelo
        # Enviamos solo campos permitidos
        response = self.client.put(
            "/api/profiles/me",
            headers=_auth_header(self.token),
            json={"name": "Still Eve", "user_id": 999},  # user_id no está en ProfileUpdate
        )
        # Con extra="forbid" el modelo de Pydantic rechazará el campo extra
        self.assertEqual(response.status_code, 422)

    def test_update_profile_without_token_returns_401(self) -> None:
        """Sin token → 401."""
        response = self.client.put(
            "/api/profiles/me",
            json={"name": "Hacker"},
        )
        self.assertEqual(response.status_code, 401)

    def test_update_profile_without_profile_creates_it(self) -> None:
        """PUT crea el Profile asociado al usuario autenticado si falta."""
        response = self.client.put(
            "/api/profiles/me",
            headers=_auth_header(self.token_no_profile),
            json={"name": "Ghost", "phone": "+999", "address": "New address"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user_id"], self.user_no_profile.id)
        self.assertEqual(data["name"], "Ghost")
        self.assertEqual(data["phone"], "+999")
        self.assertEqual(data["address"], "New address")
        self.assertIsNotNone(self.profile_repo.get_by_user_id(self.user_no_profile.id))


# ══════════════════════════════════════════════════════════════════════════════
# Auth: 401 y 403 bien diferenciados
# ══════════════════════════════════════════════════════════════════════════════


class AuthSemanticTests(unittest.TestCase):
    """Verifica 401 vs 403 en todos los endpoints protegidos."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_semantic.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)
        self.app = _make_test_app(self.repo, self.profile_repo)
        self.client = TestClient(self.app)
        self.user = _create_test_user(self.repo, "norm@example.com", "pass123")
        self.other = _create_test_user(self.repo, "other@example.com", "pass456")
        self.user_token = _login(self.client, "norm@example.com", "pass123")

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_no_token_returns_401(self) -> None:
        """Endpoints protegidos sin token → 401."""
        endpoints = [
            ("GET", "/api/auth/me"),
            ("GET", "/api/users"),
            ("GET", f"/api/users/{self.user.id}"),
            ("PUT", f"/api/users/{self.user.id}"),
            ("DELETE", f"/api/users/{self.user.id}"),
            ("GET", "/api/profiles/me"),
            ("PUT", "/api/profiles/me"),
        ]
        for method, path in endpoints:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path)
                self.assertEqual(
                    response.status_code,
                    401,
                    f"{method} {path} sin token debería ser 401",
                )

    def test_auth_error_is_401_not_403(self) -> None:
        """Errores de autenticación son 401, no 403."""
        for path in [
            "/api/auth/me",
            "/api/users",
            f"/api/users/{self.other.id}",
            f"/api/profiles/me",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path, headers=_auth_header("invalid-token"))
                self.assertEqual(
                    response.status_code,
                    401,
                    f"GET {path} con token inválido debería ser 401, no {response.status_code}",
                )

    def test_authorization_error_is_403_not_401(self) -> None:
        """Errores de autorización son 403, no 401."""
        # User normal consultando otro usuario
        response = self.client.get(
            f"/api/users/{self.other.id}",
            headers=_auth_header(self.user_token),
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()