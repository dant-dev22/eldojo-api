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


def send_student_verification_code_email(
    *,
    recipient_email: str,
    recipient_name: str | None,
    dojo_name: str | None,
    code: str,
    expires_hours: int = 24,
) -> bool:
    """Envía el correo con el código OTP de 6 dígitos para activar portal alumno.

    Fail-open: devuelve True si se entregó, False si no (SMTP no configurado,
    error de red, timeout, etc.). El caller debe interpretar False y caer en
    flujo legacy (no requerir código, permitir redeem directo).
    """

    if not recipient_email or not code:
        return False

    try:
        smtp_host, smtp_port, smtp_username, smtp_password, from_email = _require_mail_settings()
    except MailDeliveryError:
        return False

    greeting_name = recipient_name.strip() if recipient_name and recipient_name.strip() else "alumno"
    dojo_label = dojo_name.strip() if dojo_name and dojo_name.strip() else "tu dojo"
    ttl = int(expires_hours or 24)
    if ttl <= 0:
        ttl = 24

    message = EmailMessage()
    message["From"] = (
        f"{settings.smtp_from_name} <{from_email}>"
        if settings.smtp_from_name
        else from_email
    )
    message["To"] = recipient_email
    message["Subject"] = f"Tu código de activación de ElDojo: {code}"
    message.set_content(
        "\n".join(
            [
                f"Hola {greeting_name},",
                "",
                f"{dojo_label.capitalize()} te invitó a activar tu cuenta del portal del alumno.",
                "",
                "Ingresa el siguiente código en la pantalla de activación para confirmar tu identidad:",
                "",
                f"  CÓDIGO:  {code}",
                "",
                f"Este código vence en {ttl} horas y solo puede usarse una vez.",
                "Si no solicitaste activar tu cuenta, puedes ignorar este mensaje.",
            ]
        )
    )

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        return False


def send_student_invitation_link_email(
    *,
    recipient_email: str,
    recipient_name: str | None,
    dojo_name: str | None,
    invitation_link: str,
    expires_hours: int = 48,
) -> bool:
    """Envía el correo con el enlace directo de activación del portal alumno.

    Fail-open: devuelve True si se entregó, False si no (SMTP no configurado,
    error de red, timeout, etc.). El caller debe interpretar False y
    continuar sin bloquear el flujo.
    """

    if not recipient_email or not invitation_link:
        return False

    try:
        smtp_host, smtp_port, smtp_username, smtp_password, from_email = _require_mail_settings()
    except MailDeliveryError:
        return False

    greeting_name = recipient_name.strip() if recipient_name and recipient_name.strip() else "alumno"
    dojo_label = dojo_name.strip() if dojo_name and dojo_name.strip() else "tu dojo"
    ttl = int(expires_hours or 48)
    if ttl <= 0:
        ttl = 48

    message = EmailMessage()
    message["From"] = (
        f"{settings.smtp_from_name} <{from_email}>"
        if settings.smtp_from_name
        else from_email
    )
    message["To"] = recipient_email
    message["Subject"] = f"Activa tu cuenta de ElDojo - {dojo_label.capitalize()}"
    message.set_content(
        "\n".join(
            [
                f"Hola {greeting_name},",
                "",
                f"{dojo_label.capitalize()} te invitó a activar tu cuenta del portal del alumno.",
                "",
                "Abre el siguiente enlace para establecer tu contraseña y confirmar tu correo:",
                "",
                f"  {invitation_link}",
                "",
                f"Este enlace vence en {ttl} horas y solo puede usarse una vez.",
                "Si no solicitaste activar tu cuenta, puedes ignorar este mensaje.",
            ]
        )
    )

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        return False
