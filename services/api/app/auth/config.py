"""Configuración de la API mediante variables de entorno.

Todas las variables de entorno se leen en este módulo y se exponen
como constantes tipadas. Ningún otro archivo debe acceder directamente
a ``os.environ`` para leer secretos o configuración.

Las variables se pueden definir en un archivo ``.env`` en la raíz del
servicio (``services/api/.env``). Ese archivo se carga automáticamente
al importar este módulo gracias a ``python-dotenv``.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


# Cargar .env desde la raíz del servicio (services/api/.env)
_dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_dotenv_path)


_SECRET_KEY_ENV = "SECRET_KEY"
_EXPIRE_MINUTES_ENV = "ACCESS_TOKEN_EXPIRE_MINUTES"
_PASSWORD_RESET_EXPIRE_MINUTES_ENV = "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES"
_PASSWORD_RESET_FRONTEND_URL_ENV = "PASSWORD_RESET_FRONTEND_URL"
_RESEND_API_KEY_ENV = "RESEND_API_KEY"
_RESEND_FROM_EMAIL_ENV = "RESEND_FROM_EMAIL"

# ── Clave de firma JWT ──────────────────────────────────────────────────────
# La clave debe establecerse mediante la variable de entorno SECRET_KEY.
# Nunca debe estar hardcodeada ni aparecer en el repositorio.

SECRET_KEY: str = os.environ.get(_SECRET_KEY_ENV, "")

if not SECRET_KEY:
    raise RuntimeError(
        f"La variable de entorno {_SECRET_KEY_ENV} no está configurada. "
        "Consulta docs/Aprendiendo-asegurando-API.md para generar una clave segura."
    )

# ── Algoritmo de firma ──────────────────────────────────────────────────────

ALGORITHM: str = "HS256"

# ── Expiración del token ─────────────────────────────────────────────────────

ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get(_EXPIRE_MINUTES_ENV, "30")
)

ACCESS_TOKEN_EXPIRE_DELTA: timedelta = timedelta(
    minutes=ACCESS_TOKEN_EXPIRE_MINUTES
)

PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get(_PASSWORD_RESET_EXPIRE_MINUTES_ENV, "30")
)
PASSWORD_RESET_TOKEN_EXPIRE_DELTA: timedelta = timedelta(
    minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
)
PASSWORD_RESET_FRONTEND_URL: str = os.environ.get(
    _PASSWORD_RESET_FRONTEND_URL_ENV,
    "http://localhost:3000/reset-password",
).rstrip("/")
RESEND_API_KEY: str = os.environ.get(_RESEND_API_KEY_ENV, "")
RESEND_FROM_EMAIL: str = os.environ.get(
    _RESEND_FROM_EMAIL_ENV,
    "Nexova <onboarding@resend.dev>",
)