"""Utilidades de seguridad para hash y tokens Bearer."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings


class TokenDecodeError(ValueError):
    """Error al decodificar o validar un token de acceso."""


def _b64url_encode(raw_bytes: bytes) -> str:
    """Codifica bytes en Base64 URL-safe sin padding."""

    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    """Decodifica Base64 URL-safe restaurando el padding faltante."""

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _sign(signing_input: str) -> str:
    """Firma un payload usando HMAC-SHA256."""

    digest = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def hash_password(password: str) -> str:
    """Genera un hash SHA-256 simple para esta primera fase."""

    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una contraseña contra el hash almacenado."""

    return hmac.compare_digest(hash_password(password), password_hash)


def _create_token(*, user_id: int, email: str, role: str, token_type: str, ttl_seconds: int) -> tuple[str, int]:
    """Crea un token firmado con expiración y tipo explícito."""

    issued_at = int(time.time())
    expires_at = issued_at + ttl_seconds

    header = {"alg": settings.auth_algorithm, "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "token_type": token_type,
        "iat": issued_at,
        "exp": expires_at,
        "iss": settings.auth_issuer,
    }

    header_segment = _b64url_encode(
        json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_segment = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature_segment = _sign(signing_input)
    return f"{signing_input}.{signature_segment}", ttl_seconds


def create_access_token(*, user_id: int, email: str, role: str) -> tuple[str, int]:
    """Crea un token de acceso para autenticar requests."""

    return _create_token(
        user_id=user_id,
        email=email,
        role=role,
        token_type="access",
        ttl_seconds=settings.auth_access_token_expire_minutes * 60,
    )


def create_refresh_token(*, user_id: int, email: str, role: str) -> tuple[str, int]:
    """Crea un refresh token para renovar la sesión."""

    return _create_token(
        user_id=user_id,
        email=email,
        role=role,
        token_type="refresh",
        ttl_seconds=settings.auth_refresh_token_expire_days * 24 * 60 * 60,
    )


def _decode_token(token: str, *, expected_token_type: str) -> dict[str, object]:
    """Valida la firma, expiración y tipo de un token."""

    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise TokenDecodeError("Formato de token inválido") from exc

    signing_input = f"{header_segment}.{payload_segment}"
    expected_signature = _sign(signing_input)

    if not hmac.compare_digest(signature_segment, expected_signature):
        raise TokenDecodeError("Firma de token inválida")

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenDecodeError("Contenido de token inválido") from exc

    if header.get("alg") != settings.auth_algorithm:
        raise TokenDecodeError("Algoritmo de token no soportado")
    if payload.get("iss") != settings.auth_issuer:
        raise TokenDecodeError("Issuer de token inválido")
    if payload.get("token_type") != expected_token_type:
        raise TokenDecodeError("Tipo de token inválido")

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(time.time()):
        raise TokenDecodeError("Token expirado")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub.isdigit():
        raise TokenDecodeError("Subject de token inválido")

    return payload


def decode_access_token(token: str) -> dict[str, object]:
    """Valida la firma y expiración de un token de acceso."""

    return _decode_token(token, expected_token_type="access")


def decode_refresh_token(token: str) -> dict[str, object]:
    """Valida la firma y expiración de un refresh token."""

    return _decode_token(token, expected_token_type="refresh")
