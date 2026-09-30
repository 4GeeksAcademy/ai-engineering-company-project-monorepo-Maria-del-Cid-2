"""Operaciones de seguridad: hashing de contraseñas y JWT.

Toda la interacción con bcrypt y python-jose se concentra aquí.
El resto del código utiliza únicamente las funciones de este módulo,
sin importar directamente librerías criptográficas.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.hash import bcrypt

from .config import ACCESS_TOKEN_EXPIRE_DELTA, ALGORITHM, SECRET_KEY

# ── Contraseñas ──────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Genera un hash bcrypt seguro de la contraseña.

    La contraseña original NO se almacena ni se devuelve.
    Solo se conserva el hash.
    """
    return bcrypt.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Comprueba si una contraseña en texto plano coincide con su hash.

    Devuelve ``True`` si coinciden, ``False`` en cualquier otro caso.
    """
    return bcrypt.verify(plain_password, hashed_password)


# ── JWT ─────────────────────────────────────────────────────────────────────


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """Crea un JWT firmado con los datos proporcionados.

    Parámetros
    ----------
    data : dict
        Contenido del token (payload). Debe incluir al menos ``user_uuid``.
    expires_delta : timedelta | None
        Tiempo de expiración. Por defecto usa el valor de ``config.py``.

    Devuelve
    -------
    str
        Token JWT codificado y firmado.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None else ACCESS_TOKEN_EXPIRE_DELTA
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decodifica y verifica un JWT.

    Parámetros
    ----------
    token : str
        Token JWT a decodificar.

    Devuelve
    -------
    dict
        Payload del token si es válido.

    Lanza
    -----
    JWTError
        Si el token no es válido, ha expirado o la firma es incorrecta.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])