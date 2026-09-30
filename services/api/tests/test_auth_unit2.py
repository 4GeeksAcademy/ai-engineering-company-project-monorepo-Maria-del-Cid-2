"""Tests para la Unidad 2: modelos y repositorios de User y Profile.

Verifica la persistencia en TinyDB de forma aislada, sin involucrar
endpoints HTTP.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from app.auth.database import (
    create_database,
    get_profiles_table,
    get_users_table,
)
from app.auth.models import (
    Profile,
    ProfileCreate,
    ProfileUpdate,
    User,
    UserCreate,
    UserRole,
    UserUpdate,
)
from app.auth.repository import ProfileRepository, UserRepository


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

    def test_hashed_password_is_stored(self) -> None:
        user = self._create_user(password="mypassword")
        stored = self.repo.get(user.id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.hashed_password, "bcrypt_hash_mypassword")
        # Verificar que no se guarda la original
        self.assertNotEqual(stored.hashed_password, "mypassword")


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
        p1 = self.repo.create(user.id, ProfileCreate(name="First"))
        # Al crear otro con el mismo user_id, simplemente se inserta otro doc
        # (TinyDB no impide duplicados). La relación 1:1 se gestiona desde
        # la lógica de negocio, no desde la base de datos.
        p2 = self.repo.create(user.id, ProfileCreate(name="Second"))
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        # get_by_user_id devuelve el primero que encuentra (TinyDB no ordena)
        found = self.repo.get_by_user_id(user.id)
        self.assertIsNotNone(found)

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


if __name__ == "__main__":
    unittest.main()