"""Utilidades para enviar correos transaccionales del backend."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import settings


class MailDeliveryError(RuntimeError):
    """Error al intentar entregar un correo transaccional."""


def _require_mail_settings() -> tuple[str, int, str, str, str]:
    """Valida la configuración SMTP mínima para enviar correos."""

    required_values = {
        "SMTP_HOST": settings.smtp_host,
        "SMTP_USERNAME": settings.smtp_username,
        "SMTP_PASSWORD": settings.smtp_password,
        "SMTP_FROM_EMAIL": settings.smtp_from_email,
    }
    missing = [key for key, value in required_values.items() if not value]
    if missing:
        raise MailDeliveryError(
            f"Faltan variables SMTP requeridas: {', '.join(missing)}"
        )

    return (
        settings.smtp_host or "",
        settings.smtp_port,
        settings.smtp_username or "",
        settings.smtp_password or "",
        settings.smtp_from_email or "",
    )


def build_academy_confirmation_url(token: str) -> str:
    """Construye la URL pública usada en el correo de confirmación."""

    base_url = settings.academy_verification_url_base.rstrip("/")
    return f"{base_url}?token={quote(token)}"


def send_academy_confirmation_email(*, recipient_email: str, recipient_name: str, confirmation_url: str) -> None:
    """Entrega el correo de confirmación para activar una nueva academia."""

    smtp_host, smtp_port, smtp_username, smtp_password, from_email = _require_mail_settings()

    message = EmailMessage()
    message["From"] = (
        f"{settings.smtp_from_name} <{from_email}>"
        if settings.smtp_from_name
        else from_email
    )
    message["To"] = recipient_email
    message["Subject"] = "Confirma tu cuenta de ElDojo"
    message.set_content(
        "\n".join(
            [
                f"Hola {recipient_name},",
                "",
                "Ya casi tienes lista tu cuenta de ElDojo.",
                "Confirma tu correo desde este enlace para activar tu academia:",
                confirmation_url,
                "",
                f"Este enlace vence en {settings.academy_verification_token_expire_hours} horas.",
                "Si no solicitaste esta cuenta, puedes ignorar este mensaje.",
            ]
        )
    )

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailDeliveryError("No fue posible enviar el correo de confirmación") from exc
