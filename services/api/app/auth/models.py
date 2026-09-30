"""Pydantic models for Users and Profiles.

User y Profile son dos entidades separadas. Los datos de contacto
(name, phone, address) pertenecen exclusivamente a Profile.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRole(str, Enum):
    """Roles permitidos para los usuarios del sistema."""

    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"


# ── User ─────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Payload para crear un nuevo usuario.

    Solo contiene los datos que puede proporcionar el cliente:
    email y contraseña. El sistema asigna el resto.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)


class UserUpdate(BaseModel):
    """Payload para actualizar un usuario existente.

    Solo se pueden modificar campos de autorización/credenciales.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    role: UserRole | None = None


class User(BaseModel):
    """Usuario persistido, devuelto por la API.

    Nunca contiene ``hashed_password`` en respuestas HTTP.
    ``name``, ``phone`` y ``address`` pertenecen a Profile.
    """

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    email: str
    hashed_password: str
    is_active: bool = True
    role: UserRole = UserRole.USER
    created_at: datetime

    @classmethod
    def from_create(
        cls,
        user_id: int,
        payload: UserCreate,
        hashed_password: str,
    ) -> User:
        """Construye un User persistido a partir de un payload de creación.

        Parámetros
        ----------
        user_id : int
            Identificador asignado por TinyDB (doc_id).
        payload : UserCreate
            Datos proporcionados por el cliente (email + contraseña).
        hashed_password : str
            Hash bcrypt de la contraseña (nunca la original).
        """
        return cls(
            id=user_id,
            email=payload.email,
            hashed_password=hashed_password,
            is_active=True,
            role=UserRole.USER,
            created_at=datetime.now(timezone.utc),
        )


# ── Profile ──────────────────────────────────────────────────────────────────


class ProfileCreate(BaseModel):
    """Payload opcional para crear un Profile junto con un User.

    name, phone y address son opcionales porque el usuario puede
    crearse sin perfil o completarlo más tarde.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class ProfileUpdate(BaseModel):
    """Payload para actualizar los datos de un Profile."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None
    address: str | None = None


class Profile(BaseModel):
    """Perfil persistido, vinculado 1:1 con un User mediante ``user_id``."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    name: str | None = None
    phone: str | None = None
    address: str | None = None

    @classmethod
    def from_create(
        cls,
        profile_id: int,
        user_id: int,
        payload: ProfileCreate,
    ) -> Profile:
        """Construye un Profile persistido a partir de un payload opcional."""
        return cls(
            id=profile_id,
            user_id=user_id,
            name=payload.name,
            phone=payload.phone,
            address=payload.address,
        )


__all__ = [
    "UserRole",
    "UserCreate",
    "UserUpdate",
    "User",
    "ProfileCreate",
    "ProfileUpdate",
    "Profile",
]