from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.models import PasswordResetToken, RefreshToken

LOGIN = "/api/v1/accounts/login/"
CHANGE = "/api/v1/accounts/change-password/"
FORGOT = "/api/v1/accounts/forgot-password/"
RESET = "/api/v1/accounts/reset-password/"
EMAIL = "user@example.com"
OLD = "Test1234!"
NEW = "NewPass5678?"


def can_login(client, password):
    response = client.post(LOGIN, json={"email": EMAIL, "password": password})
    return response.status_code == 200


def get_reset_token(db_session):
    db_session.expire_all()
    return db_session.scalar(select(PasswordResetToken))


def test_change_password_success(client, create_user, auth_headers):
    user = create_user()

    response = client.post(
        CHANGE,
        json={"old_password": OLD, "new_password": NEW},
        headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert can_login(client, NEW)
    assert not can_login(client, OLD)


def test_change_password_wrong_old_password_returns_400(
    client, create_user, auth_headers
):
    user = create_user()

    response = client.post(
        CHANGE,
        json={"old_password": "Wrong1234!", "new_password": NEW},
        headers=auth_headers(user),
    )

    assert response.status_code == 400
    assert can_login(client, OLD)


def test_change_password_weak_new_password_returns_422(
    client, create_user, auth_headers
):
    user = create_user()

    response = client.post(
        CHANGE,
        json={"old_password": OLD, "new_password": "weak"},
        headers=auth_headers(user),
    )

    assert response.status_code == 422


def test_change_password_requires_authorization(client):
    response = client.post(CHANGE, json={"old_password": OLD, "new_password": NEW})

    assert response.status_code in (401, 403)


def test_change_password_revokes_refresh_tokens(
    client, db_session, create_user, auth_headers
):
    user = create_user()
    can_login(client, OLD)
    assert db_session.scalar(select(RefreshToken)) is not None

    client.post(
        CHANGE,
        json={"old_password": OLD, "new_password": NEW},
        headers=auth_headers(user),
    )

    db_session.expire_all()
    assert db_session.scalar(select(RefreshToken)) is None


def test_forgot_password_sends_email_for_active_user(
    client, db_session, create_user, sent_reset_emails
):
    create_user()

    response = client.post(FORGOT, json={"email": EMAIL})

    assert response.status_code == 200
    assert sent_reset_emails == [(EMAIL, get_reset_token(db_session).token)]


def test_forgot_password_unknown_email_returns_same_response(
    client, sent_reset_emails
):
    response = client.post(FORGOT, json={"email": "no@example.com"})

    assert response.status_code == 200
    assert sent_reset_emails == []


def test_forgot_password_inactive_user_sends_nothing(
    client, create_user, sent_reset_emails
):
    create_user(is_active=False)

    response = client.post(FORGOT, json={"email": EMAIL})

    assert response.status_code == 200
    assert sent_reset_emails == []


def test_forgot_password_twice_replaces_token(client, db_session, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})
    first = get_reset_token(db_session).token

    client.post(FORGOT, json={"email": EMAIL})

    assert get_reset_token(db_session).token != first


def test_reset_password_success(client, db_session, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})
    token = get_reset_token(db_session).token

    response = client.post(
        RESET, json={"email": EMAIL, "token": token, "new_password": NEW}
    )

    assert response.status_code == 200
    assert can_login(client, NEW)
    assert not can_login(client, OLD)
    assert get_reset_token(db_session) is None


def test_reset_password_wrong_token_returns_400(client, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})

    response = client.post(
        RESET, json={"email": EMAIL, "token": "wrong", "new_password": NEW}
    )

    assert response.status_code == 400
    assert can_login(client, OLD)


def test_reset_password_expired_token_returns_400(client, db_session, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})
    token = get_reset_token(db_session)
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        RESET, json={"email": EMAIL, "token": token.token, "new_password": NEW}
    )

    assert response.status_code == 400


def test_reset_password_weak_password_returns_422(client, db_session, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})
    token = get_reset_token(db_session).token

    response = client.post(
        RESET, json={"email": EMAIL, "token": token, "new_password": "weak"}
    )

    assert response.status_code == 422


def test_reset_password_token_cannot_be_reused(client, db_session, create_user):
    create_user()
    client.post(FORGOT, json={"email": EMAIL})
    token = get_reset_token(db_session).token
    client.post(RESET, json={"email": EMAIL, "token": token, "new_password": NEW})

    response = client.post(
        RESET, json={"email": EMAIL, "token": token, "new_password": "Other1234!x"}
    )

    assert response.status_code == 400
    