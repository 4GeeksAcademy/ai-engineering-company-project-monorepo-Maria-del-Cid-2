"""Tests para la Unidad 2: modelos y repositorios de User y Profile.

Verifica la persistencia en TinyDB de forma aislada, sin involucrar
endpoints HTTP.
"""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest import mock

from pydantic import ValidationError

from app.auth.database import (
    create_database,
    get_password_reset_tokens_table,
    get_profiles_table,
    get_users_table,
)
from app.auth.models import (
    PasswordResetToken,
    Profile,
    ProfileCreate,
    ProfileUpdate,
    User,
    UserCreate,
    UserRole,
    UserUpdate,
)
from app.auth.repository import (
    LastAdminError,
    PasswordResetTokenRepository,
    ProfileDuplicateError,
    ProfilePersistenceError,
    ProfileRepository,
    UserRepository,
)


class UserModelTests(unittest.TestCase):
    """Tests del modelo User: validación, rol por defecto y campos."""

    def test_user_has_no_profile_fields(self) -> None:
        """User no debe contener name, phone ni address."""
        for field in ("name", "phone", "address"):
            with self.subTest(field=field):
                self.assertNotIn(field, User.model_fields)

    def test_user_requires_email_and_password_on_create(self) -> None:
        payload = UserCreate(email="user@example.com", password="secret")
        self.assertEqual(payload.email, "user@example.com")
        self.assertEqual(payload.password, "secret")

    def test_user_create_rejects_invalid_email(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate(email="not-an-email", password="secret")

    def test_user_create_rejects_empty_password(self) -> None:
        with self.assertRaises(ValidationError):
            UserCreate(email="user@example.com", password="")

    def test_default_role_is_user(self) -> None:
        self.assertEqual(UserRole.USER.value, "user")

    def test_role_enum_values(self) -> None:
        values = {role.value for role in UserRole}
        self.assertEqual(values, {"admin", "manager", "user"})

    def test_user_from_create_sets_defaults(self) -> None:
        payload = UserCreate(email="new@example.com", password="hashedpass123")
        user = User.from_create(42, payload, "bcrypt_hash_here")
        self.assertEqual(user.id, 42)
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.hashed_password, "bcrypt_hash_here")
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, UserRole.USER)
        self.assertIsInstance(user.created_at, datetime)

    def test_user_from_create_does_not_store_original_password(self) -> None:
        payload = UserCreate(email="a@b.com", password="original_secret")
        user = User.from_create(1, payload, "bcrypt:")
        self.assertNotEqual(user.hashed_password, "original_secret")
        self.assertNotIn("original_secret", user.hashed_password)

    def test_user_from_create_uses_utc(self) -> None:
        payload = UserCreate(email="a@b.com", password="x")
        user = User.from_create(1, payload, "hash")
        self.assertEqual(user.created_at.tzinfo, timezone.utc)


class UserRepositoryTests(unittest.TestCase):
    """Tests del repositorio User con TinyDB real (archivo temporal)."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test.json"
        self.database = create_database(self.db_path)
        self.repo = UserRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def _create_user(
        self,
        email: str = "user@example.com",
        password: str = "secret123",
    ) -> User:
        payload = UserCreate(email=email, password=password)
        return self.repo.create(payload, "bcrypt_hash_" + password)

    def test_create_user_returns_user_with_id(self) -> None:
        user = self._create_user()
        self.assertEqual(user.id, 1)
        self.assertEqual(user.email, "user@example.com")
        self.assertTrue(user.is_active)
        self.assertEqual(user.role, UserRole.USER)

    def test_get_user_by_id_returns_user(self) -> None:
        created = self._create_user()
        retrieved = self.repo.get(created.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, created.id)
        self.assertEqual(retrieved.email, created.email)

    def test_get_user_by_id_missing_returns_none(self) -> None:
        self.assertIsNone(self.repo.get(999))

    def test_get_user_by_email_returns_user(self) -> None:
        self._create_user(email="find@example.com")
        found = self.repo.get_by_email("find@example.com")
        self.assertIsNotNone(found)
        self.assertEqual(found.email, "find@example.com")

    def test_get_user_by_email_missing_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_by_email("nonexistent@example.com"))

    def test_list_users_returns_all(self) -> None:
        self._create_user(email="a@example.com")
        self._create_user(email="b@example.com")
        users = self.repo.list()
        self.assertEqual(len(users), 2)
        emails = {u.email for u in users}
        self.assertIn("a@example.com", emails)
        self.assertIn("b@example.com", emails)

    def test_list_users_empty_returns_empty_list(self) -> None:
        self.assertEqual(self.repo.list(), [])

    def test_update_user_email(self) -> None:
        user = self._create_user()
        updated = self.repo.update(user.id, UserUpdate(email="new@example.com"))
        self.assertIsNotNone(updated)
        self.assertEqual(updated.email, "new@example.com")

    def test_update_user_role(self) -> None:
        user = self._create_user()
        updated = self.repo.update(user.id, UserUpdate(role=UserRole.ADMIN))
        self.assertIsNotNone(updated)
        self.assertEqual(updated.role, UserRole.ADMIN)

    def test_update_user_no_changes_returns_original(self) -> None:
        user = self._create_user()
        updated = self.repo.update(user.id, UserUpdate())
        self.assertIsNotNone(updated)
        self.assertEqual(updated.email, user.email)
        self.assertEqual(updated.role, user.role)

    def test_update_nonexistent_user_returns_none(self) -> None:
        self.assertIsNone(self.repo.update(999, UserUpdate(email="x@y.com")))

    def test_delete_user_removes_user(self) -> None:
        user = self._create_user()
        self.assertTrue(self.repo.delete(user.id))
        self.assertIsNone(self.repo.get(user.id))

    def test_delete_nonexistent_user_returns_false(self) -> None:
        self.assertFalse(self.repo.delete(999))

    def _create_admin(self, email: str, *, is_active: bool = True) -> User:
        return self.repo.create_with_attrs(
            UserCreate(email=email, password="secret123"),
            "hash",
            role=UserRole.ADMIN,
            is_active=is_active,
        )

    def test_update_rejects_demoting_last_active_admin(self) -> None:
        admin = self._create_admin("admin@example.com")
        with self.assertRaises(LastAdminError):
            self.repo.update(admin.id, UserUpdate(role=UserRole.MANAGER))
        self.assertEqual(self.repo.get(admin.id).role, UserRole.ADMIN)

    def test_update_rejection_does_not_apply_other_fields(self) -> None:
        admin = self._create_admin("admin@example.com")
        with self.assertRaises(LastAdminError):
            self.repo.update(
                admin.id,
                UserUpdate(email="changed@example.com", role=UserRole.USER),
            )
        persisted = self.repo.get(admin.id)
        self.assertEqual(persisted.email, "admin@example.com")
        self.assertEqual(persisted.role, UserRole.ADMIN)

    def test_inactive_admin_does_not_count_when_demoting(self) -> None:
        admin = self._create_admin("admin@example.com")
        inactive = self._create_admin("inactive@example.com", is_active=False)
        with self.assertRaises(LastAdminError):
            self.repo.update(admin.id, UserUpdate(role=UserRole.USER))
        self.assertEqual(self.repo.get(admin.id).role, UserRole.ADMIN)
        self.assertEqual(self.repo.get(inactive.id).role, UserRole.ADMIN)

    def test_update_allows_demoting_admin_when_another_active_admin_exists(self) -> None:
        first = self._create_admin("first@example.com")
        self._create_admin("second@example.com")
        updated = self.repo.update(first.id, UserUpdate(role=UserRole.MANAGER))
        self.assertEqual(updated.role, UserRole.MANAGER)
        self.assertEqual(self.repo.get(first.id).role, UserRole.MANAGER)

    def test_update_allows_demoting_inactive_admin_without_other_admins(self) -> None:
        inactive = self._create_admin("inactive@example.com", is_active=False)
        updated = self.repo.update(inactive.id, UserUpdate(role=UserRole.USER))
        self.assertEqual(updated.role, UserRole.USER)

    def test_delete_rejects_last_active_admin_before_cleanup(self) -> None:
        admin = self._create_admin("admin@example.com")
        cleanup = mock.Mock()
        with self.assertRaises(LastAdminError):
            self.repo.delete(admin.id, before_delete=cleanup)
        cleanup.assert_not_called()
        self.assertIsNotNone(self.repo.get(admin.id))

    def test_delete_runs_cleanup_then_removes_user(self) -> None:
        first = self._create_admin("first@example.com")
        self._create_admin("second@example.com")
        cleanup = mock.Mock(side_effect=lambda: self.assertIsNotNone(self.repo.get(first.id)))
        self.assertTrue(self.repo.delete(first.id, before_delete=cleanup))
        cleanup.assert_called_once_with()
        self.assertIsNone(self.repo.get(first.id))

    def test_delete_keeps_user_when_cleanup_fails(self) -> None:
        first = self._create_admin("first@example.com")
        self._create_admin("second@example.com")
        cleanup = mock.Mock(side_effect=ProfilePersistenceError)
        with self.assertRaises(ProfilePersistenceError):
            self.repo.delete(first.id, before_delete=cleanup)
        self.assertIsNotNone(self.repo.get(first.id))

    def test_concurrent_mutual_demotion_leaves_one_active_admin(self) -> None:
        first = self._create_admin("first@example.com")
        second = self._create_admin("second@example.com")
        barrier = Barrier(2)

        def demote(user_id: int) -> bool:
            barrier.wait()
            try:
                self.repo.update(user_id, UserUpdate(role=UserRole.USER))
                return True
            except LastAdminError:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(demote, [first.id, second.id]))

        self.assertEqual(results.count(True), 1)
        remaining = [u for u in self.repo.list() if u.role == UserRole.ADMIN and u.is_active]
        self.assertEqual(len(remaining), 1)

    def test_hashed_password_is_stored(self) -> None:
        user = self._create_user(password="mypassword")
        stored = self.repo.get(user.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.hashed_password, "bcrypt_hash_mypassword")
        # Verificar que no se guarda la original
        self.assertNotEqual(stored.hashed_password, "mypassword")

    def test_update_password_nonexistent_user_returns_none(self) -> None:
        """update_password retorna None para usuario inexistente."""
        result = self.repo.update_password(99999, "irrelevant_hash")
        self.assertIsNone(result)


class ProfileModelTests(unittest.TestCase):
    """Tests del modelo Profile."""

    def test_profile_has_required_fields(self) -> None:
        """Profile debe tener user_id, name, phone, address."""
        for field in ("user_id", "name", "phone", "address"):
            with self.subTest(field=field):
                self.assertIn(field, Profile.model_fields)

    def test_profile_from_create_links_to_user(self) -> None:
        payload = ProfileCreate(name="John", phone="+34123456789", address="C/ Example 123")
        profile = Profile.from_create(10, 5, payload)
        self.assertEqual(profile.id, 10)
        self.assertEqual(profile.user_id, 5)
        self.assertEqual(profile.name, "John")
        self.assertEqual(profile.phone, "+34123456789")
        self.assertEqual(profile.address, "C/ Example 123")

    def test_profile_from_create_without_optional_fields(self) -> None:
        payload = ProfileCreate()
        profile = Profile.from_create(1, 1, payload)
        self.assertIsNone(profile.name)
        self.assertIsNone(profile.phone)
        self.assertIsNone(profile.address)


class ProfileRepositoryTests(unittest.TestCase):
    """Tests del repositorio Profile con TinyDB real (archivo temporal)."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test.json"
        self.database = create_database(self.db_path)
        self.repo = ProfileRepository(self.database)
        self.user_repo = UserRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def _create_user(self, email: str = "u@example.com") -> User:
        return self.user_repo.create(
            UserCreate(email=email, password="pass"),
            "hash",
        )

    def test_create_profile(self) -> None:
        user = self._create_user()
        profile = self.repo.create(
            user.id,
            ProfileCreate(name="Alice", phone="123", address="Addr"),
        )
        self.assertEqual(profile.user_id, user.id)
        self.assertEqual(profile.name, "Alice")
        self.assertEqual(profile.phone, "123")
        self.assertEqual(profile.address, "Addr")

    def test_get_profile_by_user_id(self) -> None:
        user = self._create_user()
        created = self.repo.create(user.id, ProfileCreate(name="Bob"))
        found = self.repo.get_by_user_id(user.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, created.id)
        self.assertEqual(found.name, "Bob")

    def test_get_profile_by_user_id_missing_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_by_user_id(999))

    def test_get_profile_by_id(self) -> None:
        user = self._create_user()
        created = self.repo.create(user.id, ProfileCreate(name="Carol"))
        found = self.repo.get(created.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Carol")

    def test_profile_read_error_is_normalized(self) -> None:
        table = mock.Mock()
        table.get.side_effect = OSError("storage detail")
        with mock.patch("app.auth.repository.get_profiles_table", return_value=table):
            with self.assertRaises(ProfilePersistenceError) as context:
                self.repo.get_by_user_id(1)
        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_profile_create_error_is_normalized(self) -> None:
        table = mock.Mock()
        table.__iter__ = mock.Mock(return_value=iter(()))
        table.get.return_value = None  # get_by_user_id → no existe perfil previo
        table.insert.side_effect = OSError("storage detail")
        with mock.patch("app.auth.repository.get_profiles_table", return_value=table):
            with self.assertRaises(ProfilePersistenceError) as context:
                self.repo.create(1, ProfileCreate(name="Alice"))
        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_profile_update_error_is_normalized(self) -> None:
        table = mock.Mock()
        table.get.return_value = {
            "id": 1,
            "user_id": 1,
            "name": "Alice",
            "phone": None,
            "address": None,
        }
        table.update.side_effect = OSError("storage detail")
        with mock.patch("app.auth.repository.get_profiles_table", return_value=table):
            with self.assertRaises(ProfilePersistenceError) as context:
                self.repo.update(1, ProfileUpdate(name="Updated"))
        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_profile_delete_error_is_normalized(self) -> None:
        table = mock.Mock()
        table.remove.side_effect = OSError("storage detail")
        with mock.patch("app.auth.repository.get_profiles_table", return_value=table):
            with self.assertRaises(ProfilePersistenceError) as context:
                self.repo.delete_by_user_id(1)
        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_update_profile(self) -> None:
        user = self._create_user()
        self.repo.create(user.id, ProfileCreate(name="Old", phone="", address=""))
        updated = self.repo.update(
            user.id,
            ProfileUpdate(name="New Name", phone="+34 999", address="New Address"),
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.phone, "+34 999")
        self.assertEqual(updated.address, "New Address")

    def test_update_profile_no_user_returns_none(self) -> None:
        self.assertIsNone(
            self.repo.update(999, ProfileUpdate(name="No one"))
        )

    def test_delete_profile_by_user_id(self) -> None:
        user = self._create_user()
        self.repo.create(user.id, ProfileCreate(name="ToDelete"))
        self.assertTrue(self.repo.delete_by_user_id(user.id))
        self.assertIsNone(self.repo.get_by_user_id(user.id))

    def test_delete_profile_nonexistent_user_returns_false(self) -> None:
        self.assertFalse(self.repo.delete_by_user_id(999))

    def test_one_to_one_relationship(self) -> None:
        """Un usuario tiene como máximo un Profile."""
        user = self._create_user()
        self.repo.create(user.id, ProfileCreate(name="First"))
        # Crear un segundo Profile para el mismo user_id debe rechazarse
        with self.assertRaises(ProfileDuplicateError):
            self.repo.create(user.id, ProfileCreate(name="Second"))
        # El perfil original debe permanecer intacto
        found = self.repo.get_by_user_id(user.id)
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "First")

    def test_create_after_delete_allows_new_profile(self) -> None:
        """Eliminar y luego crear un nuevo Profile para el mismo user_id funciona."""
        user = self._create_user()
        self.repo.create(user.id, ProfileCreate(name="Original"))
        self.assertTrue(self.repo.delete_by_user_id(user.id))
        self.assertIsNone(self.repo.get_by_user_id(user.id))
        # Ahora debería poder crearse otro
        new_profile = self.repo.create(user.id, ProfileCreate(name="Replacement"))
        self.assertIsNotNone(new_profile)
        self.assertEqual(new_profile.name, "Replacement")
        self.assertEqual(new_profile.user_id, user.id)

    def test_create_duplicate_is_atomic_does_not_create_partial_profile(self) -> None:
        """Si se rechaza un duplicado, no debe quedar ningún rastro."""
        user = self._create_user()
        self.repo.create(user.id, ProfileCreate(name="Original"))
        # Contar cuántos docs hay en la tabla antes del intento
        from app.auth.database import get_profiles_table
        table = get_profiles_table(self.database)
        count_before = len(table)
        with self.assertRaises(ProfileDuplicateError):
            self.repo.create(user.id, ProfileCreate(name="Intruder"))
        # La tabla no debe tener documentos extra
        self.assertEqual(len(table), count_before)
        # Y el perfil original sigue intacto
        found = self.repo.get_by_user_id(user.id)
        self.assertEqual(found.name, "Original")

    def test_concurrent_profile_creation_leaves_exactly_one_profile(self) -> None:
        """Dos hilos creando un Profile para el mismo user_id → solo uno triunfa."""
        user = self._create_user()
        barrier = Barrier(2)

        def create_profile() -> bool:
            barrier.wait()
            try:
                self.repo.create(user.id, ProfileCreate(name="Concurrent"))
                return True
            except ProfileDuplicateError:
                return False

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: create_profile(), range(2)))

        self.assertEqual(results.count(True), 1)
        # Solo debe haber 1 profile en la tabla
        from app.auth.database import get_profiles_table
        table = get_profiles_table(self.database)
        profiles_for_user = [doc for doc in table if doc.get("user_id") == user.id]
        self.assertEqual(len(profiles_for_user), 1)

    def test_multiple_users_have_isolated_profiles(self) -> None:
        """Los perfiles de distintos usuarios están aislados."""
        user_a = self._create_user(email="a@example.com")
        user_b = self._create_user(email="b@example.com")
        self.repo.create(user_a.id, ProfileCreate(name="Alice"))
        self.repo.create(user_b.id, ProfileCreate(name="Bob"))
        profile_a = self.repo.get_by_user_id(user_a.id)
        profile_b = self.repo.get_by_user_id(user_b.id)
        self.assertEqual(profile_a.name, "Alice")
        self.assertEqual(profile_b.name, "Bob")


class UserProfileIntegrationTests(unittest.TestCase):
    """Tests de integración: relación User ↔ Profile y eliminación."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test.json"
        self.database = create_database(self.db_path)
        self.user_repo = UserRepository(self.database)
        self.profile_repo = ProfileRepository(self.database)

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_user_with_profile_cascade_delete(self) -> None:
        """Eliminar un User y verificar que podemos eliminar su Profile."""
        user = self.user_repo.create(
            UserCreate(email="delete@example.com", password="pass"),
            "hash",
        )
        self.profile_repo.create(
            user.id,
            ProfileCreate(name="DeleteMe", phone="123", address="Addr"),
        )
        # Primero eliminar el Profile
        profile_deleted = self.profile_repo.delete_by_user_id(user.id)
        self.assertTrue(profile_deleted)
        self.assertIsNone(self.profile_repo.get_by_user_id(user.id))
        # Después eliminar el User
        user_deleted = self.user_repo.delete(user.id)
        self.assertTrue(user_deleted)
        self.assertIsNone(self.user_repo.get(user.id))


class UserRoleTests(unittest.TestCase):
    """Tests específicos de roles."""

    def test_only_three_roles_exist(self) -> None:
        roles = list(UserRole)
        self.assertEqual(len(roles), 3)
        self.assertIn(UserRole.ADMIN, roles)
        self.assertIn(UserRole.MANAGER, roles)
        self.assertIn(UserRole.USER, roles)

    def test_role_user_is_default(self) -> None:
        """El rol por defecto en User.from_create es USER."""
        payload = UserCreate(email="default@example.com", password="x")
        user = User.from_create(1, payload, "hash")
        self.assertEqual(user.role, UserRole.USER)

    def test_user_can_be_admin(self) -> None:
        payload = UserCreate(email="admin@example.com", password="x")
        user = User.from_create(1, payload, "hash")
        # Simular cambio de rol vía repositorio
        user.role = UserRole.ADMIN
        self.assertEqual(user.role, UserRole.ADMIN)
        self.assertEqual(user.role.value, "admin")

    def test_user_can_be_manager(self) -> None:
        payload = UserCreate(email="manager@example.com", password="x")
        user = User.from_create(1, payload, "hash")
        user.role = UserRole.MANAGER
        self.assertEqual(user.role, UserRole.MANAGER)
        self.assertEqual(user.role.value, "manager")

    def test_invalid_role_value_rejected_by_enum(self) -> None:
        with self.assertRaises(ValueError):
            UserRole("superadmin")

    def test_update_with_invalid_role_rejected(self) -> None:
        with self.assertRaises(ValueError):
            UserUpdate(role="superadmin")  # type: ignore


class PasswordResetTokenRepositoryTests(unittest.TestCase):
    """Tests del repositorio de tokens de reseteo de contraseña."""

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_tokens.json"
        self.database = create_database(self.db_path)
        self.repo = PasswordResetTokenRepository(self.database)
        self.now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.token = self.repo.create(
            user_id=1,
            token_hash="abc123hash",
            created_at=self.now,
            expires_at=self.now + timedelta(hours=1),
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_get_by_hash_returns_token(self) -> None:
        """Recuperar por hash devuelve el token."""
        result = self.repo.get_by_hash("abc123hash")
        self.assertIsNotNone(result)
        self.assertEqual(result.user_id, 1)
        self.assertEqual(result.token_hash, "abc123hash")

    def test_get_by_hash_missing_returns_none(self) -> None:
        """Hash inexistente → None."""
        result = self.repo.get_by_hash("nonexistent")
        self.assertIsNone(result)

    def test_consume_returns_true(self) -> None:
        """Consumir un token válido retorna True."""
        result = self.repo.consume(self.token.id, self.now + timedelta(minutes=5))
        self.assertTrue(result)

    def test_consume_returns_false_when_already_consumed(self) -> None:
        """Consumir dos veces el mismo token → False la segunda."""
        self.repo.consume(self.token.id, self.now + timedelta(minutes=5))
        result = self.repo.consume(self.token.id, self.now + timedelta(minutes=10))
        self.assertFalse(result)

    def test_consume_returns_false_when_expired(self) -> None:
        """Token expirado → consume() retorna False."""
        result = self.repo.consume(self.token.id, self.now + timedelta(hours=2))
        self.assertFalse(result)

    def test_consume_nonexistent_returns_false(self) -> None:
        """Token inexistente → consume() retorna False."""
        result = self.repo.consume(99999, self.now)
        self.assertFalse(result)

    def test_get_by_hash_is_thread_safe_with_consume(self) -> None:
        """get_by_hash y consume comparten el lock; no hay corrupción de datos."""
        token = self.repo.create(
            user_id=2,
            token_hash="xyz789hash",
            created_at=self.now,
            expires_at=self.now + timedelta(hours=1),
        )
        barrier = Barrier(2)

        def consume_worker() -> bool:
            barrier.wait()
            return self.repo.consume(token.id, self.now + timedelta(minutes=5))

        def get_hash_worker() -> PasswordResetToken | None:
            barrier.wait()
            return self.repo.get_by_hash(token.token_hash)

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(consume_worker)
            f2 = pool.submit(get_hash_worker)
            consume_result = f1.result()
            get_result = f2.result()

        # consume debe marcar el token existente y válido → True
        self.assertTrue(consume_result)
        # get_by_hash nunca pierde el documento bajo el lock compartido
        self.assertIsNotNone(get_result)
        self.assertIsInstance(get_result, PasswordResetToken)
        # El estado final es consistente: el token queda consumido
        final = self.repo.get_by_hash(token.token_hash)
        self.assertIsNotNone(final)
        self.assertIsNotNone(final.used_at)

    def test_invalidate_for_user_marks_unused_tokens_as_used(self) -> None:
        """invalidate_for_user() pública sella tokens no usados."""
        self.repo.invalidate_for_user(1, self.now)
        result = self.repo.get_by_hash("abc123hash")
        self.assertIsNotNone(result)
        self.assertIsNotNone(result.used_at)


class ProfileEdgeCaseTests(unittest.TestCase):
    """Tests de casos borde en ProfileRepository.get/update.

    Cubre ramas no alcanzadas por ProfileRepositoryTests:
    - get() por doc_id normaliza errores
    - update() retorna early cuando no hay cambios
    - update() re-lanza ProfilePersistenceError
    """

    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "auth_test_profile_errors.json"
        self.database = create_database(self.db_path)
        self.repo = ProfileRepository(self.database)
        self.user_repo = UserRepository(self.database)
        # Creamos un usuario para poder crear perfiles reales
        self.user = self.user_repo.create(
            UserCreate(email="test@example.com", password="x"),
            "bcrypt_hash",
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temp_dir.cleanup()

    def test_profile_get_error_is_normalized(self) -> None:
        """get() por doc_id normaliza OSError a ProfilePersistenceError."""
        table = mock.Mock()
        table.get.side_effect = OSError("storage detail")
        with mock.patch("app.auth.repository.get_profiles_table", return_value=table):
            with self.assertRaises(ProfilePersistenceError) as context:
                self.repo.get(1)
        self.assertIsInstance(context.exception.__cause__, OSError)

    def test_profile_update_no_changes_returns_profile(self) -> None:
        """update() retorna el perfil sin persistir cuando no hay cambios."""
        profile = self.repo.create(self.user.id, ProfileCreate(name="Alice"))
        result = self.repo.update(self.user.id, ProfileUpdate())
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Alice")

    def test_profile_update_re_raises_persistence_error(self) -> None:
        """update() re-lanza ProfilePersistenceError si get_by_user_id falló."""
        with mock.patch.object(
            self.repo, "get_by_user_id",
            side_effect=ProfilePersistenceError("already broken"),
        ):
            with self.assertRaises(ProfilePersistenceError):
                self.repo.update(self.user.id, ProfileUpdate(name="Bob"))


if __name__ == "__main__":
    unittest.main()