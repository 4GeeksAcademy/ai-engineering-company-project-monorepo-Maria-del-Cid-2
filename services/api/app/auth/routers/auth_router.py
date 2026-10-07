"""Auth HTTP endpoints — /api/auth.

Este router implementa los endpoints públicos y protegidos de
autenticación.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import (
    get_current_user,
    get_password_reset_service,
    get_profile_repository,
    get_repository,
)
from app.auth.email import EmailDeliveryError
from app.auth.models import Profile, User
from app.auth.repository import ProfileRepository, UserRepository
from app.auth.password_reset import PasswordResetError, PasswordResetService
from app.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GenericMessageResponse,
    PasswordResetRequest,
    TokenResponse,
    UserMeResponse,
)
from app.auth.service import AuthService, AuthenticationError

router = APIRouter(prefix="/api/auth", tags=["auth"])

_FORGOT_PASSWORD_MESSAGE = (
    "Si existe una cuenta asociada, recibirás instrucciones para restablecer la contraseña."
)


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


@router.post("/forgot-password", response_model=GenericMessageResponse)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    service: PasswordResetService = Depends(get_password_reset_service),
) -> GenericMessageResponse:
    """Request a reset email without revealing whether the account exists."""
    try:
        service.request_reset(
            str(payload.email),
            request.client.host if request.client else None,
        )
    except EmailDeliveryError:
        # The public response remains identical for existing and unknown emails.
        pass
    return GenericMessageResponse(message=_FORGOT_PASSWORD_MESSAGE)


@router.post("/reset-password", response_model=GenericMessageResponse)
def reset_password(
    request: Request,
    payload: PasswordResetRequest,
    service: PasswordResetService = Depends(get_password_reset_service),
) -> GenericMessageResponse:
    try:
        service.reset_password(
            payload.token,
            payload.new_password,
            request.client.host if request.client else None,
        )
    except PasswordResetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        ) from exc
    return GenericMessageResponse(message="Password reset successfully")


@router.post("/change-password", response_model=GenericMessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: PasswordResetService = Depends(get_password_reset_service),
) -> GenericMessageResponse:
    try:
        service.change_password(
            current_user.id,
            payload.current_password,
            payload.new_password,
        )
    except PasswordResetError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from exc
    return GenericMessageResponse(message="Password changed successfully")