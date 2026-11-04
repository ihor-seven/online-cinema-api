import logging

from src.celery_app import celery_app
from src.database import SessionLocal
from src.services.cleanup import cleanup_expired_tokens

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.delete_expired_tokens")
def delete_expired_tokens() -> dict[str, int]:
    db = SessionLocal()
    try:
        deleted = cleanup_expired_tokens(db)
    finally:
        db.close()

    logger.info("Expired tokens deleted: %s", deleted)
    return deleted
