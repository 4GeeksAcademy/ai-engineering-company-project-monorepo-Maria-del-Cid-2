"""Tests para la Unidad 1: configuración, hashing bcrypt y JWT.

Estos tests verifican los módulos de forma aislada (no requieren
endpoints HTTP ni base de datos). Se centran en:

- Configuración desde variables de entorno.
- Hashing y verificación de contraseñas con bcrypt.
- Creación, decodificación y validación de tokens JWT.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta, timezone

# ── Establecer variables de entorno antes de importar los módulos ──
# config.py lee las variables en el momento de la importación.
os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from jose import JWTError, jwt

import app.auth.config as auth_config
from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class ConfigTests(unittest.TestCase):
    """Tests sobre la lectura de variables de entorno."""

    def test_config_reads_secret_key_from_environment(self) -> None:
        self.assertEqual(auth_config.SECRET_KEY, "test-secret-key-for-unit-tests")

    def test_config_reads_expire_minutes_from_environment(self) -> None:
        self.assertEqual(auth_config.ACCESS_TOKEN_EXPIRE_MINUTES, 60)

    def test_config_creates_expire_delta(self) -> None:
        self.assertEqual(auth_config.ACCESS_TOKEN_EXPIRE_DELTA, timedelta(minutes=60))

    def test_config_algorithm_is_hs256(self) -> None:
        self.assertEqual(auth_config.ALGORITHM, "HS256")


class PasswordHashingTests(unittest.TestCase):
    """Tests sobre bcrypt: hash y verificación."""

    def test_hash_is_different_from_original_password(self) -> None:
        password = "MiContraseñaSegura2024!"
        hashed = hash_password(password)
        self.assertNotEqual(hashed, password)

    def test_hash_starts_with_bcrypt_prefix(self) -> None:
        hashed = hash_password("test")
        self.assertTrue(hashed.startswith("$2"))

    def test_correct_password_verifies_ok(self) -> None:
        password = "supersecret"
        hashed = hash_password(password)
        self.assertTrue(verify_password(password, hashed))

    def test_wrong_password_does_not_verify(self) -> None:
        hashed = hash_password("correct")
        self.assertFalse(verify_password("wrong", hashed))

    def test_two_hashes_of_same_password_are_different(self) -> None:
        """bcrypt usa sal aleatoria, por lo que dos hashes de la misma
        contraseña deben ser diferentes entre sí."""
        password = "samepassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        self.assertNotEqual(hash1, hash2)

    def test_empty_password_does_not_verify(self) -> None:
        hashed = hash_password("something")
        self.assertFalse(verify_password("", hashed))


class JwtTests(unittest.TestCase):
    """Tests sobre creación y decodificación de JWT."""

    def test_create_token_returns_string_with_dots(self) -> None:
        token = create_access_token({"user_uuid": "123"})
        # Un JWT tiene tres partes separadas por puntos
        self.assertEqual(len(token.split(".")), 3)

    def test_decode_valid_token_returns_payload(self) -> None:
        payload = {"user_uuid": "abc-123"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        self.assertEqual(decoded["user_uuid"], "abc-123")

    def test_token_contains_expiration(self) -> None:
        token = create_access_token({"user_uuid": "1"})
        decoded = jwt.decode(
            token,
            auth_config.SECRET_KEY,
            algorithms=[auth_config.ALGORITHM],
        )
        self.assertIn("exp", decoded)

    def test_token_expiration_is_in_the_future(self) -> None:
        token = create_access_token({"user_uuid": "1"})
        decoded = jwt.decode(
            token,
            auth_config.SECRET_KEY,
            algorithms=[auth_config.ALGORITHM],
        )
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        self.assertTrue(exp > datetime.now(timezone.utc))

    def test_token_with_custom_expiration(self) -> None:
        short = timedelta(seconds=1)
        token = create_access_token({"user_uuid": "1"}, expires_delta=short)
        decoded = jwt.decode(
            token,
            auth_config.SECRET_KEY,
            algorithms=[auth_config.ALGORITHM],
        )
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        self.assertTrue(exp > datetime.now(timezone.utc))

    def test_decode_invalid_token_raises_error(self) -> None:
        with self.assertRaises(JWTError):
            decode_access_token("invalid.token.here")

    def test_decode_token_with_wrong_key_raises_error(self) -> None:
        token = jwt.encode(
            {"user_uuid": "1"},
            "wrong-key",
            algorithm=auth_config.ALGORITHM,
        )
        with self.assertRaises(JWTError):
            decode_access_token(token)

    def test_decode_expired_token_raises_error(self) -> None:
        # Crear un token con expiración en el pasado
        expired_payload = {
            "user_uuid": "1",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jwt.encode(
            expired_payload,
            auth_config.SECRET_KEY,
            algorithm=auth_config.ALGORITHM,
        )
        with self.assertRaises(JWTError):
            decode_access_token(token)

    def test_token_without_user_uuid_still_decodes(self) -> None:
        token = create_access_token({"other": "data"})
        decoded = decode_access_token(token)
        self.assertNotIn("user_uuid", decoded)


if __name__ == "__main__":
    unittest.main()