"""Auth service — lógica de autenticación entre HTTP y repositorio.

Separa la responsabilidad de autenticación (verificar credenciales,
generar tokens) de la persistencia (UserRepository) y de la capa HTTP
(router/dependencias).

Conceptualmente:

    router (futuro)
         ↓
    AuthService   ← este archivo
         ↓
    UserRepository
         ↓
    TinyDB
"""

from __future__ import annotations

from .models import User
from .repository import UserRepository
from .security import create_access_token, verify_password
from .config import ACCESS_TOKEN_EXPIRE_DELTA


class AuthenticationError(Exception):
    """Error genérico de autenticación.

    Se usa para cualquier fallo: email inexistente, contraseña
    incorrecta o usuario inactivo. El mensaje es siempre el mismo
    para no permitir enumeración de usuarios.
    """


class AuthService:
    """Servicio de autenticación.

    No accede directamente a TinyDB. Delega en UserRepository para
    la persistencia y en security.py para hashing/JWT.
    """

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def authenticate(self, email: str, password: str) -> User:
        """Autentica un usuario por email + contraseña.

        Pasos:
        1. Buscar usuario por email en el repositorio.
        2. Verificar contraseña contra el hash almacenado.
        3. Verificar que el usuario está activo.

        Cualquier fallo → ``AuthenticationError`` con mensaje genérico.
        """
        user = self._repository.get_by_email(email)
        if user is None:
            raise AuthenticationError("Invalid credentials")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid credentials")

        if not user.is_active:
            raise AuthenticationError("Invalid credentials")

        return user

    def create_token(self, user: User) -> str:
        """Genera un JWT para el usuario autenticado.

        El token contiene:
        - ``sub``: ID del usuario (str) — identificador principal
        - ``exp``: timestamp de expiración (manejado por create_access_token)
        """
        return create_access_token(data={"sub": str(user.id)})