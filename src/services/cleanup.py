from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.models import ActivationToken, PasswordResetToken, RefreshToken

EXPIRING_MODELS = (
    ("activation_tokens", ActivationToken),
    ("password_reset_tokens", PasswordResetToken),
    ("refresh_tokens", RefreshToken),
)


def cleanup_expired_tokens(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Delete all expired tokens. Returns how many rows were deleted per table."""
    now = now or datetime.now(timezone.utc)
    deleted: dict[str, int] = {}

    for table_name, model in EXPIRING_MODELS:
        result = db.execute(delete(model).where(model.expires_at < now))
        deleted[table_name] = result.rowcount

    db.commit()
    return deleted
