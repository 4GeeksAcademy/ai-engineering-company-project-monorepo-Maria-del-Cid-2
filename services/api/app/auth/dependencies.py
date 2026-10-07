"""FastAPI dependencies for authentication.

Proporciona ``get_current_user`` como dependencia reutilizable que
los routers de la Unidad 4 podrán inyectar con ``Depends()``.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, ExpiredSignatureError

from .database import get_database
from .models import User
from .repository import UserRepository
from .security import decode_access_token

# ── OAuth2PasswordBearer ────────────────────────────────────────────────────
# Configura el esquema Bearer para Swagger/OpenAPI.
# ``tokenUrl`` apuntará al futuro endpoint /auth/login.
# Cuando un endpoint con Depends(get_current_user) recibe una request
# sin token (o con token inválido), FastAPI/OAuth2 responde con 401
# y el header WWW-Authenticate: Bearer.

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_repository() -> UserRepository:
    """Proporciona un UserRepository conectado a la BD de auth.

    Se cierra la BD al finalizar la request. Los tests pueden
    sobrescribir esta dependencia con ``dependency_overrides``
    para usar una BD temporal.
    """
    database = get_database()
    try:
        yield UserRepository(database)
    finally:
        database.close()


def get_current_user(
    token: str = Depends(_oauth2_scheme),
    repository: UserRepository = Depends(get_repository),
) -> User:
    """Dependencia FastAPI que devuelve el usuario autenticado.

    Extrae y valida el Bearer token, busca el usuario y verifica
    que está activo. Cualquier fallo → 401.

    Uso esperado::

        @router.get("/me")
        def read_me(user: User = Depends(get_current_user)):
            return user
    """
    # ── Decodificar JWT ────────────────────────────────────────────────
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Extraer sub (user id) ──────────────────────────────────────────
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Buscar usuario ─────────────────────────────────────────────────
    user = repository.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Verificar activo ───────────────────────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("credentials_version") != user.credentials_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_profile_repository() -> ProfileRepository:
    """Proporciona un ProfileRepository conectado a la BD de auth."""
    from .repository import ProfileRepository

    database = get_database()
    try:
        yield ProfileRepository(database)
    finally:
        database.close()


def get_password_reset_service():
    """Provide password reset orchestration with one shared auth DB handle."""
    from .email import ResendEmailSender
    from .password_reset import PasswordResetService
    from .repository import (
        PasswordResetAuditLogRepository,
        PasswordResetRateLimitRepository,
        PasswordResetTokenRepository,
    )

    database = get_database()
    try:
        yield PasswordResetService(
            UserRepository(database),
            PasswordResetTokenRepository(database),
            ResendEmailSender(),
            rate_limits=PasswordResetRateLimitRepository(database),
            audit_log=PasswordResetAuditLogRepository(database),
        )
    finally:
        database.close()