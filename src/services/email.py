import smtplib
from email.message import EmailMessage

from src.config import settings


def send_email(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.send_message(message)


def send_activation_email(email: str, token: str) -> None:
    send_email(
        to=email,
        subject="Activate your Online Cinema account",
        body=(
            "Welcome to Online Cinema!\n\n"
            "To activate your account, send this token together with your email "
            "to POST /api/v1/accounts/activate/ :\n\n"
            f"{token}\n\n"
            "The token is valid for 24 hours."
        ),
    )
    