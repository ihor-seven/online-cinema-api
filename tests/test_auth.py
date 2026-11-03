from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from src.config import settings
from src.models import RefreshToken, User, UserGroup, UserGroupEnum
from src.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)

LOGIN = "/api/v1/accounts/login/"
REFRESH = "/api/v1/accounts/refresh/"
LOGOUT = "/api/v1/accounts/logout/"
ME = "/api/v1/accounts/me/"
EMAIL = "user@example.com"
PASSWORD = "Test1234!"


@pytest.fixture
def make_user(db_session):
    def _make(is_active: bool = True) -> User:
        group = db_session.scalar(
            select(UserGroup).where(UserGroup.name == UserGroupEnum.USER)
        )
        if group is None:
            group = UserGroup(name=UserGroupEnum.USER)
            db_session.add(group)
            db_session.flush()
        user = User(
            email=EMAIL,
            hashed_password=hash_password(PASSWORD),
            is_active=is_active,
            group_id=group.id,
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make


def login(client):
    return client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})


def test_login_success_returns_tokens_and_stores_refresh(
    client, db_session, make_user
):
    make_user()

    response = login(client)

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    stored = db_session.scalar(select(RefreshToken))
    assert stored.token == data["refresh_token"]


def test_login_wrong_password_returns_401(client, make_user):
    make_user()

    response = client.post(LOGIN, json={"email": EMAIL, "password": "Wrong1234!"})

    assert response.status_code == 401


def test_login_unknown_email_returns_401(client):
    response = client.post(LOGIN, json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 401


def test_login_inactive_user_returns_403(client, make_user):
    make_user(is_active=False)

    response = login(client)

    assert response.status_code == 403


def test_refresh_returns_working_access_token(client, make_user):
    make_user()
    refresh_token = login(client).json()["refresh_token"]

    response = client.post(REFRESH, json={"refresh_token": refresh_token})

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    me = client.get(ME, headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_refresh_with_garbage_returns_401(client):
    response = client.post(REFRESH, json={"refresh_token": "garbage"})

    assert response.status_code == 401


def test_refresh_with_access_token_returns_401(client, make_user):
    make_user()
    access_token = login(client).json()["access_token"]

    response = client.post(REFRESH, json={"refresh_token": access_token})

    assert response.status_code == 401


def test_logout_deletes_refresh_token(client, db_session, make_user):
    make_user()
    refresh_token = login(client).json()["refresh_token"]

    response = client.post(LOGOUT, json={"refresh_token": refresh_token})

    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.scalar(select(RefreshToken)) is None


def test_refresh_after_logout_returns_401(client, make_user):
    make_user()
    refresh_token = login(client).json()["refresh_token"]
    client.post(LOGOUT, json={"refresh_token": refresh_token})

    response = client.post(REFRESH, json={"refresh_token": refresh_token})

    assert response.status_code == 401


def test_logout_unknown_token_returns_401(client):
    response = client.post(LOGOUT, json={"refresh_token": "unknown"})

    assert response.status_code == 401


def test_me_without_token_is_rejected(client):
    response = client.get(ME)

    assert response.status_code in (401, 403)


def test_me_with_refresh_token_returns_401(client, make_user):
    make_user()
    refresh_token = login(client).json()["refresh_token"]

    response = client.get(ME, headers={"Authorization": f"Bearer {refresh_token}"})

    assert response.status_code == 401


def test_decode_token_accepts_valid_token():
    token = create_access_token(42)

    assert decode_token(token, "access")["sub"] == "42"


def test_decode_token_rejects_wrong_type():
    token, _ = create_refresh_token(42)

    with pytest.raises(ValueError):
        decode_token(token, "access")


def test_decode_token_rejects_expired_token():
    payload = {
        "sub": "1",
        "type": "access",
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)

    with pytest.raises(ValueError):
        decode_token(token, "access")