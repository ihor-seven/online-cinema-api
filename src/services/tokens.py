import secrets
from datetime import datetime, timedelta, timezone

from src.models import ActivationToken, PasswordResetToken

ACTIVATION_TOKEN_TTL_HOURS = 24
PASSWORD_RESET_TOKEN_TTL_HOURS = 1


def build_activation_token(user_id: int) -> ActivationToken:
    return ActivationToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=ACTIVATION_TOKEN_TTL_HOURS),
    )


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < datetime.now(timezone.utc)


PASSWORD_RESET_TOKEN_TTL_HOURS = 1


def build_password_reset_token(user_id: int) -> PasswordResetToken:
    return PasswordResetToken(
        user_id=user_id,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=PASSWORD_RESET_TOKEN_TTL_HOURS),
    )