"""Utilidades mínimas de seguridad para la API."""

from __future__ import annotations

import hashlib


def hash_password(password: str) -> str:
    """Genera un hash SHA-256 simple para entornos de desarrollo.

    Nota: esto deja la API lista para pruebas rápidas, pero en producción se
    recomienda migrar a Argon2 o BCrypt cuando se implemente autenticación real.
    """

    return hashlib.sha256(password.encode("utf-8")).hexdigest()
