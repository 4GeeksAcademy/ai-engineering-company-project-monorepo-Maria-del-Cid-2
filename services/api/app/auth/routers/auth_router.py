"""Auth HTTP endpoints — /api/auth.

Este router implementa los endpoints públicos y protegidos de
autenticación.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import get_current_user, get_profile_repository, get_repository
from app.auth.models import Profile, User
from app.auth.repository import ProfileRepository, UserRepository
from app.auth.schemas import TokenResponse, UserMeResponse
from app.auth.service import AuthService, AuthenticationError

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    repository: UserRepository = Depends(get_repository),
) -> TokenResponse:
    """Autentica un usuario y devuelve un JWT (Bearer token).

    Acepta credenciales mediante ``application/x-www-form-urlencoded``
    (compatible con OAuth2PasswordBearer / Swagger Authorize).

    - ``username`` = email del usuario
    - ``password`` = contraseña

    Cualquier credencial incorrecta → 401 con mensaje genérico.
    """
    service = AuthService(repository)
    try:
        user = service.authenticate(form_data.username, form_data.password)
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = service.create_token(user)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserMeResponse)
def read_current_user(
    current_user: User = Depends(get_current_user),
    profile_repository: ProfileRepository = Depends(get_profile_repository),
) -> UserMeResponse:
    """Devuelve la información del usuario autenticado.

    Incluye:
    - email, role, is_active, created_at
    - Profile (name, phone, address) si existe, o ``None``

    Nunca devuelve ``hashed_password`` ni el token.
    """
    profile = profile_repository.get_by_user_id(current_user.id)
    return UserMeResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        role=current_user.role,
        created_at=current_user.created_at,
        profile=profile,
    )