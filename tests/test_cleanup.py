from datetime import datetime, timedelta, timezone

from sqlalchemy import select

import src.tasks
from src.celery_app import celery_app
from src.models import ActivationToken, PasswordResetToken, RefreshToken, User
from src.services.cleanup import cleanup_expired_tokens


def hours_from_now(hours: int) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def tokens(db_session, model):
    db_session.expire_all()
    return db_session.scalars(select(model)).all()


def test_expired_activation_tokens_are_deleted_and_valid_ones_kept(
    db_session, create_user
):
    expired_user = create_user(email="expired@example.com", is_active=False)
    valid_user = create_user(email="valid@example.com", is_active=False)
    db_session.add_all(
        [
            ActivationToken(user_id=expired_user.id, token="expired", expires_at=hours_from_now(-1)),
            ActivationToken(user_id=valid_user.id, token="valid", expires_at=hours_from_now(1)),
        ]
    )
    db_session.commit()

    deleted = cleanup_expired_tokens(db_session)

    assert deleted["activation_tokens"] == 1
    assert [t.token for t in tokens(db_session, ActivationToken)] == ["valid"]


def test_expired_password_reset_and_refresh_tokens_are_deleted(db_session, create_user):
    user = create_user()
    other = create_user(email="other@example.com")
    db_session.add_all(
        [
            PasswordResetToken(user_id=user.id, token="old-reset", expires_at=hours_from_now(-1)),
            PasswordResetToken(user_id=other.id, token="new-reset", expires_at=hours_from_now(1)),
            RefreshToken(user_id=user.id, token="old-refresh", expires_at=hours_from_now(-24)),
            RefreshToken(user_id=user.id, token="new-refresh", expires_at=hours_from_now(24)),
        ]
    )
    db_session.commit()

    deleted = cleanup_expired_tokens(db_session)

    assert deleted["password_reset_tokens"] == 1
    assert deleted["refresh_tokens"] == 1
    assert [t.token for t in tokens(db_session, PasswordResetToken)] == ["new-reset"]
    assert [t.token for t in tokens(db_session, RefreshToken)] == ["new-refresh"]


def test_cleanup_with_nothing_to_delete(db_session):
    deleted = cleanup_expired_tokens(db_session)

    assert deleted == {
        "activation_tokens": 0,
        "password_reset_tokens": 0,
        "refresh_tokens": 0,
    }


def test_cleanup_keeps_the_users(db_session, create_user):
    user = create_user(is_active=False)
    db_session.add(
        ActivationToken(user_id=user.id, token="expired", expires_at=hours_from_now(-1))
    )
    db_session.commit()

    cleanup_expired_tokens(db_session)

    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.id == user.id)) is not None


def test_user_can_get_new_activation_token_after_cleanup(
    client, db_session, create_user, sent_emails
):
    user = create_user(email="user@example.com", is_active=False)
    db_session.add(
        ActivationToken(user_id=user.id, token="expired", expires_at=hours_from_now(-1))
    )
    db_session.commit()
    cleanup_expired_tokens(db_session)

    response = client.post(
        "/api/v1/accounts/resend-activation/", json={"email": "user@example.com"}
    )

    assert response.status_code == 200
    assert len(tokens(db_session, ActivationToken)) == 1
    assert len(sent_emails) == 1


def test_celery_task_deletes_expired_tokens(
    monkeypatch, session_factory, db_session, create_user
):
    user = create_user(is_active=False)
    db_session.add(
        ActivationToken(user_id=user.id, token="expired", expires_at=hours_from_now(-1))
    )
    db_session.commit()
    monkeypatch.setattr("src.tasks.SessionLocal", session_factory)

    result = src.tasks.delete_expired_tokens()

    assert result["activation_tokens"] == 1
    assert tokens(db_session, ActivationToken) == []


def test_task_is_registered_and_scheduled_in_celery_beat():
    assert "src.tasks.delete_expired_tokens" in celery_app.tasks

    schedule = celery_app.conf.beat_schedule["delete-expired-tokens"]
    assert schedule["task"] == "src.tasks.delete_expired_tokens"
    assert schedule["schedule"] > 0
    