"""Profiles HTTP endpoints — /api/profiles.

Endpoints protegidos que permiten al usuario autenticado gestionar
su propio perfil (Profile).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_current_user, get_profile_repository
from app.auth.models import Profile, ProfileUpdate, User
from app.auth.repository import ProfileRepository
from app.auth.schemas import ProfileCreate  # Reutilizamos el modelo de creación

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


# ── GET /api/profiles/me ────────────────────────────────────────────────────


@router.get("/me", response_model=Profile)
def read_my_profile(
    current_user: User = Depends(get_current_user),
    profile_repository: ProfileRepository = Depends(get_profile_repository),
) -> Profile:
    """Devuelve el Profile del usuario autenticado.

    **Protegido** — requiere token Bearer válido.

    - Usa ``current_user.id`` para buscar el Profile.
    - Si no existe Profile → 404.
    - No permite que el cliente especifique qué user_id consultar.
    """
    profile = profile_repository.get_by_user_id(current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )
    return profile


# ── PUT /api/profiles/me ────────────────────────────────────────────────────


@router.put("/me", response_model=Profile)
def update_my_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    profile_repository: ProfileRepository = Depends(get_profile_repository),
) -> Profile:
    """Actualiza el Profile del usuario autenticado.

    **Protegido** — requiere token Bearer válido.

    Solo permite modificar:
    - ``name``
    - ``phone``
    - ``address``

    Nunca permite modificar ``id`` ni ``user_id``.

    Si no existe Profile → 404.
    """
    existing = profile_repository.get_by_user_id(current_user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create a profile via POST /api/users with profile data.",
        )

    updated = profile_repository.update(current_user.id, payload)
    assert updated is not None  # Acabamos de verificar que existe
    return updated