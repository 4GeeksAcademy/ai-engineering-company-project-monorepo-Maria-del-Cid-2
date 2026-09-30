"""Response schemas for auth endpoints.

Estos modelos definen qué datos se exponen en las respuestas HTTP.
Nunca incluyen ``hashed_password`` ni otros secretos.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.models import Profile, ProfileCreate, UserRole


# ── Auth ────────────────────────────────────────────────────────────────────


class TokenResponse(BaseModel):
    """Respuesta del endpoint de login (OAuth2 compatible)."""

    access_token: str
    token_type: str = "bearer"


class UserMeResponse(BaseModel):
    """Información del usuario autenticado, incluyendo Profile opcional.

    Nunca incluye ``hashed_password``.
    """

    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime
    profile: Profile | None = None


# ── Users ───────────────────────────────────────────────────────────────────


class UserResponse(BaseModel):
    """Representación segura de User para respuestas HTTP.

    Nunca incluye ``hashed_password``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_active: bool
    role: UserRole
    created_at: datetime


class UserCreateRequest(BaseModel):
    """Payload para crear un usuario (y opcionalmente su Profile).

    - ``password`` se hashea antes de almacenar (nunca en texto plano).
    - ``role`` por defecto es ``user``.
    - ``profile`` puede incluir ``name``, ``phone`` y ``address``.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1)
    is_active: bool = True
    role: UserRole = UserRole.USER
    profile: ProfileCreate | None = None


class UserUpdateRequest(BaseModel):
    """Payload para actualizar un usuario.

    - ``password`` NO se acepta en este endpoint (reservado para futuro).
    - ``role`` solo puede cambiarlo un admin.
    - Nunca se acepta ``hashed_password`` directamente.
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    role: UserRole | None = None


__all__ = [
    "TokenResponse",
    "UserMeResponse",
    "UserResponse",
    "UserCreateRequest",
    "UserUpdateRequest",
]