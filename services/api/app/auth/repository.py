"""TinyDB repository operations for Users and Profiles.

Sigue el patrón de SupplierRepository pero operando sobre tablas
independientes de TinyDB (``users`` y ``profiles``) en lugar de la
tabla por defecto.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any

from tinydb import Query, TinyDB
from tinydb.table import Document, Table

from .database import get_profiles_table, get_users_table
from .models import Profile, ProfileCreate, ProfileUpdate, User, UserCreate, UserRole, UserUpdate

_user_creation_lock = Lock()


class DuplicateEmailError(Exception):
    """Raised when a user email is already registered."""


class UserRepository:
    """Persistence adapter for User records in TinyDB."""

    def __init__(self, database: TinyDB) -> None:
        self._db = database

    @property
    def _table(self) -> Table:
        return get_users_table(self._db)

    # ── CRUD ─────────────────────────────────────────────────────────────

    def create(self, payload: UserCreate, hashed_password: str) -> User:
        user_id = max((doc.doc_id for doc in self._table), default=0) + 1
        user = User.from_create(user_id, payload, hashed_password)
        self._table.insert(
            Document(user.model_dump(mode="json"), doc_id=user_id)
        )
        return user

    def create_with_attrs(
        self,
        payload: UserCreate,
        hashed_password: str,
        *,
        is_active: bool = True,
        role: UserRole = UserRole.USER,
    ) -> User:
        """Crea un usuario con atributos personalizados.

        Permite especificar ``is_active`` y ``role`` en lugar de usar
        los valores por defecto de ``from_create``.
        """
        user_id = max((doc.doc_id for doc in self._table), default=0) + 1
        user = User.from_create(user_id, payload, hashed_password, is_active=is_active, role=role)
        self._table.insert(
            Document(user.model_dump(mode="json"), doc_id=user_id)
        )
        return user

    def create_if_email_available(
        self,
        payload: UserCreate,
        hashed_password: str,
    ) -> User:
        """Create a standard user atomically with respect to this process.

        The process-wide lock prevents duplicate registrations when the API
        runs with a single worker. It does not coordinate multiple processes.
        """
        with _user_creation_lock:
            if self.get_by_email(str(payload.email)) is not None:
                raise DuplicateEmailError
            return self.create(payload, hashed_password)

    def get(self, user_id: int) -> User | None:
        record = self._table.get(doc_id=user_id)
        return User.model_validate(record) if record is not None else None

    def get_by_email(self, email: str) -> User | None:
        UserQuery = Query()
        record = self._table.get(UserQuery.email == email)
        return User.model_validate(record) if record is not None else None

    def list(self) -> list[User]:
        return [User.model_validate(doc) for doc in self._table.all()]

    def update(self, user_id: int, payload: UserUpdate) -> User | None:
        user = self.get(user_id)
        if user is None:
            return None

        updates: dict[str, Any] = {}
        if payload.email is not None:
            updates["email"] = payload.email
        if payload.role is not None:
            updates["role"] = payload.role.value

        if not updates:
            return user

        self._table.update(updates, doc_ids=[user_id])
        return self.get(user_id)

    def delete(self, user_id: int) -> bool:
        """Elimina el usuario por su ID.

        Nota: el Profile vinculado debe eliminarse por separado
        mediante ProfileRepository.delete_by_user_id().
        """
        return bool(self._table.remove(doc_ids=[user_id]))


class ProfileRepository:
    """Persistence adapter for Profile records in TinyDB."""

    def __init__(self, database: TinyDB) -> None:
        self._db = database

    @property
    def _table(self) -> Table:
        return get_profiles_table(self._db)

    # ── CRUD ─────────────────────────────────────────────────────────────

    def create(self, user_id: int, payload: ProfileCreate) -> Profile:
        profile_id = max((doc.doc_id for doc in self._table), default=0) + 1
        profile = Profile.from_create(profile_id, user_id, payload)
        self._table.insert(
            Document(profile.model_dump(mode="json"), doc_id=profile_id)
        )
        return profile

    def get(self, profile_id: int) -> Profile | None:
        record = self._table.get(doc_id=profile_id)
        return Profile.model_validate(record) if record is not None else None

    def get_by_user_id(self, user_id: int) -> Profile | None:
        ProfileQuery = Query()
        record = self._table.get(ProfileQuery.user_id == user_id)
        return Profile.model_validate(record) if record is not None else None

    def update(self, user_id: int, payload: ProfileUpdate) -> Profile | None:
        """Actualiza el Profile asociado a un user_id.

        Busca el Profile por user_id (relación 1:1) y aplica los cambios.
        """
        profile = self.get_by_user_id(user_id)
        if profile is None:
            return None

        updates: dict[str, Any] = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.phone is not None:
            updates["phone"] = payload.phone
        if payload.address is not None:
            updates["address"] = payload.address

        if not updates:
            return profile

        ProfileQuery = Query()
        self._table.update(updates, ProfileQuery.user_id == user_id)
        return self.get_by_user_id(user_id)

    def delete_by_user_id(self, user_id: int) -> bool:
        """Elimina el Profile asociado a un user_id."""
        ProfileQuery = Query()
        return bool(self._table.remove(ProfileQuery.user_id == user_id))