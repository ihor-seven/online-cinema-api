from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from src.models import ActivationToken, User

REGISTER = "/api/v1/accounts/register/"
ACTIVATE = "/api/v1/accounts/activate/"
RESEND = "/api/v1/accounts/resend-activation/"
EMAIL = "user@example.com"


def register(client):
    client.post(REGISTER, json={"email": EMAIL, "password": "Test1234!"})


def get_token(db_session) -> ActivationToken:
    db_session.expire_all()
    return db_session.scalar(select(ActivationToken))


def test_register_sends_activation_email(client, db_session, sent_emails):
    register(client)

    assert len(sent_emails) == 1
    assert sent_emails[0][0] == EMAIL
    assert sent_emails[0][1] == get_token(db_session).token


def test_activate_success(client, db_session):
    register(client)
    token = get_token(db_session).token

    response = client.post(ACTIVATE, json={"email": EMAIL, "token": token})

    assert response.status_code == 200
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == EMAIL))
    assert user.is_active is True
    assert db_session.scalar(select(ActivationToken)) is None


def test_activate_wrong_token_returns_400(client, db_session):
    register(client)

    response = client.post(ACTIVATE, json={"email": EMAIL, "token": "wrong"})

    assert response.status_code == 400
    db_session.expire_all()
    user = db_session.scalar(select(User).where(User.email == EMAIL))
    assert user.is_active is False


def test_activate_unknown_email_returns_400(client):
    response = client.post(ACTIVATE, json={"email": "no@example.com", "token": "x"})

    assert response.status_code == 400


def test_activate_expired_token_returns_400(client, db_session):
    register(client)
    token = get_token(db_session)
    token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    response = client.post(ACTIVATE, json={"email": EMAIL, "token": token.token})

    assert response.status_code == 400


def test_activate_already_active_user_returns_400(client, db_session):
    register(client)
    token = get_token(db_session).token
    client.post(ACTIVATE, json={"email": EMAIL, "token": token})

    response = client.post(ACTIVATE, json={"email": EMAIL, "token": token})

    assert response.status_code == 400


def test_resend_creates_new_token_and_sends_email(client, db_session, sent_emails):
    register(client)
    old_token = get_token(db_session).token

    response = client.post(RESEND, json={"email": EMAIL})

    assert response.status_code == 200
    new_token = get_token(db_session).token
    assert new_token != old_token
    assert len(sent_emails) == 2
    assert sent_emails[1] == (EMAIL, new_token)


def test_resend_works_after_token_expired(client, db_session):
    register(client)
    token = get_token(db_session)
    token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    client.post(RESEND, json={"email": EMAIL})
    new_token = get_token(db_session)

    response = client.post(ACTIVATE, json={"email": EMAIL, "token": new_token.token})
    assert response.status_code == 200


def test_resend_for_active_user_sends_nothing(client, db_session, sent_emails):
    register(client)
    token = get_token(db_session).token
    client.post(ACTIVATE, json={"email": EMAIL, "token": token})

    response = client.post(RESEND, json={"email": EMAIL})

    assert response.status_code == 200
    assert len(sent_emails) == 1


def test_resend_for_unknown_email_returns_same_response(client, sent_emails):
    response = client.post(RESEND, json={"email": "no@example.com"})

    assert response.status_code == 200
    assert sent_emails == []
