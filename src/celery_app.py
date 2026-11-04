from celery import Celery

from src.config import settings

celery_app = Celery(
    "online_cinema",
    broker=settings.redis_url,
    include=["src.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "delete-expired-tokens": {
            "task": "src.tasks.delete_expired_tokens",
            "schedule": float(settings.token_cleanup_interval_seconds),
        },
    },
)
