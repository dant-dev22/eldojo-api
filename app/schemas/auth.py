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


class AcademyRegisterRequest(BaseModel):
    """Payload público para crear una academia y su admin inicial."""

    academy_name: str = Field(min_length=2, max_length=150)
    admin_first_name: str = Field(min_length=2, max_length=100)
    admin_last_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("academy_name", "admin_first_name", "admin_last_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Elimina espacios sobrantes en campos de texto visibles."""

        return " ".join(value.strip().split())

    @field_validator("email")
    @classmethod
    def normalize_academy_register_email(cls, value: str) -> str:
        """Normaliza el email del admin inicial."""

        return value.strip().lower()


class AcademyRegisterPendingResponse(BaseModel):
    """Respuesta cuando una academia queda pendiente de confirmar correo."""

    status: str = "pending_confirmation"
    email: str
    email_sent: bool
    message: str
    verification_expires_in_hours: int
    pending_session_ticket: str
    pending_session_expires_in_hours: int
    polling_interval_seconds: int


class AcademyConfirmRequest(BaseModel):
    """Payload para confirmar una cuenta de academia con un token."""

    token: str = Field(min_length=16, max_length=512)


class AcademyResendConfirmationRequest(BaseModel):
    """Payload para reenviar el correo de confirmación."""

    email: str = Field(min_length=5, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_resend_email(cls, value: str) -> str:
        """Normaliza el email para reenviar confirmaciones."""

        return value.strip().lower()


class AcademyPendingSessionRequest(BaseModel):
    """Payload para consultar o canjear un ticket temporal de login."""

    ticket: str = Field(min_length=16, max_length=512)


class AcademyPendingSessionStatusResponse(BaseModel):
    """Estado del ticket temporal asociado al registro pendiente."""

    status: str
    message: str


class TutorialStateUpdateRequest(BaseModel):
    """Payload para actualizar el estado del tutorial inicial."""

    first_time: bool


class TokenResponse(BaseModel):
    """Respuesta de autenticación exitosa."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserRead


class SessionTicketCreateResponse(BaseModel):
    """Respuesta al crear un ticket de sincronización entre subdominios."""

    ticket: str
    ttl_seconds: int


class SessionTicketRedeemRequest(BaseModel):
    """Payload para canjear un ticket de sincronización y obtener tokens."""

    ticket: str = Field(min_length=16, max_length=512)
