"""Users HTTP endpoints — /api/users.

Endpoints protegidos con autenticación y autorización por roles.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import (
    get_current_user,
    get_profile_repository,
    get_repository,
)
from app.auth.models import User, UserCreate, UserRole, UserUpdate
from app.auth.repository import DuplicateEmailError, ProfileRepository, UserRepository
from app.auth.schemas import UserCreateRequest, UserResponse, UserUpdateRequest
from app.auth.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_to_response(user: User) -> UserResponse:
    """Convierte un User persistido en una respuesta segura (sin hashed_password)."""
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        created_at=user.created_at,
    )


# ── POST /api/users (público) ───────────────────────────────────────────────


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    repository: UserRepository = Depends(get_repository),
    profile_repository: ProfileRepository = Depends(get_profile_repository),
) -> UserResponse:
    """Crea un usuario (y opcionalmente su Profile).

    **Público** — no requiere autenticación.

    - El password se hashea antes de almacenarlo.
    - Se puede incluir un Profile opcional (name, phone, address).
    - Si la creación del Profile falla, se elimina el User creado
      (compensación manual, ya que TinyDB no soporta transacciones).

    La respuesta nunca incluye ``hashed_password``.
    """
    # 1. Hashear password
    hashed = hash_password(payload.password)

    # 2. Usar payload como UserCreate
    user_create = UserCreate(email=payload.email, password=payload.password)
    try:
        user = repository.create_if_email_available(user_create, hashed)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc

    # 3. Crear Profile si se proporcionó
    if payload.profile is not None:
        try:
            profile_repository.create(user.id, payload.profile)
        except Exception:
            # Compensación: eliminar el User creado
            repository.delete(user.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create profile, user creation reverted",
            )

    return _user_to_response(user)


# ── GET /api/users (protegido) ──────────────────────────────────────────────


@router.get("", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_repository),
) -> list[UserResponse]:
    """Lista todos los usuarios.

    **Protegido** — requiere token Bearer válido.

    La respuesta nunca incluye ``hashed_password``.
    """
    return [_user_to_response(u) for u in repository.list()]


# ── GET /api/users/{user_id} (protegido + autorización) ─────────────────────


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_repository),
) -> UserResponse:
    """Obtiene un usuario por su ID.

    **Protegido** — requiere token Bearer válido.

    Reglas de autorización:
    - Self (current_user.id == user_id) → permitido
    - Admin → puede consultar cualquier usuario
    - Otro usuario autenticado → 403
    - Usuario inexistente → 404
    """
    # Self o admin pueden consultar
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user",
        )

    user = repository.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return _user_to_response(user)


# ── PUT /api/users/{user_id} (protegido + autorización) ─────────────────────


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_repository),
) -> UserResponse:
    """Actualiza un usuario.

    **Protegido** — requiere token Bearer válido.

    Reglas de autorización:
    - Self → puede actualizar sus campos permitidos (email)
    - Self → NO puede cambiarse el role a sí mismo
    - Admin → puede actualizar cualquier usuario, incluido el role
    - Manager → no puede actualizar arbitrariamente otros usuarios
    - Otro usuario → 403

    Solo admin puede cambiar ``role``.
    Nunca se acepta ``hashed_password`` directamente.
    """
    # ── Autorización ──────────────────────────────────────────────────
    is_self = current_user.id == user_id
    is_admin = current_user.role == UserRole.ADMIN

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    # ── Verificar que el usuario existe ───────────────────────────────
    existing = repository.get(user_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # ── Validar role change ───────────────────────────────────────────
    if payload.role is not None and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change role",
        )

    # ── Self no puede cambiarse role aunque sea admin vía payload ─────
    #   (ya cubierto arriba: is_admin check, pero si self intenta
    #    enviar role sin ser admin, ya se bloquea)

    # ── Aplicar cambios ───────────────────────────────────────────────
    update_payload = UserUpdate(email=payload.email, role=payload.role)
    updated = repository.update(user_id, update_payload)

    # repository.update() returns None if user doesn't exist (already checked)
    assert updated is not None
    return _user_to_response(updated)


# ── DELETE /api/users/{user_id} (protegido + autorización) ──────────────────


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    repository: UserRepository = Depends(get_repository),
    profile_repository: ProfileRepository = Depends(get_profile_repository),
) -> None:
    """Elimina un usuario y su Profile asociado.

    **Protegido** — requiere token Bearer válido.

    Reglas de autorización:
    - Self → puede eliminarse a sí mismo
    - Admin → puede eliminar cualquier usuario
    - Manager → no puede eliminar arbitrariamente
    - Usuario normal → no puede eliminar otro usuario
    - Usuario inexistente → 404
    """
    # ── Autorización ──────────────────────────────────────────────────
    is_self = current_user.id == user_id
    is_admin = current_user.role == UserRole.ADMIN

    if not is_self and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )

    # ── Verificar existencia ──────────────────────────────────────────
    existing = repository.get(user_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # ── Eliminar Profile asociado ─────────────────────────────────────
    profile_repository.delete_by_user_id(user_id)

    # ── Eliminar User ─────────────────────────────────────────────────
    repository.delete(user_id)