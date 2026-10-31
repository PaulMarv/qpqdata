"""SMTP transport shared by authentication and development verification."""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings


class DeliveryError(Exception):
    pass


def deliver_message(settings: Settings, message: EmailMessage) -> None:
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise DeliveryError("Development email delivery unavailable.") from None
