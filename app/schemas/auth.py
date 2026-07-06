"""Schemas de autenticación."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Credenciales para iniciar sesión."""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normaliza el email para evitar variaciones triviales."""

        return value.strip().lower()


class RefreshRequest(BaseModel):
    """Payload para renovar la sesión usando el refresh token."""

    refresh_token: str = Field(min_length=32)


class StudentRegisterRequest(BaseModel):
    """Payload para vincular un alumno existente a sus credenciales."""

    unique_code: str = Field(min_length=4, max_length=20)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("unique_code")
    @classmethod
    def normalize_unique_code(cls, value: str) -> str:
        """Normaliza el código único para evitar errores triviales."""

        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_register_email(cls, value: str) -> str:
        """Normaliza el email del registro."""

        return value.strip().lower()


class TokenResponse(BaseModel):
    """Respuesta de autenticación exitosa."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserRead
