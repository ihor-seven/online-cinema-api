from sqlalchemy import select

from src.models import ActivationToken, User
from src.security import validate_password_strength
import pytest

URL = "/api/v1/accounts/register/"
VALID = {"email": "user@example.com", "password": "Test1234!"}


def test_register_success(client):
    response = client.post(URL, json=VALID)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "user@example.com"
    assert data["is_active"] is False
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_creates_inactive_user_and_token(client, db_session):
    client.post(URL, json=VALID)

    user = db_session.scalar(select(User).where(User.email == "user@example.com"))
    assert user is not None
    assert user.hashed_password != VALID["password"]

    token = db_session.scalar(
        select(ActivationToken).where(ActivationToken.user_id == user.id)
    )
    assert token is not None


def test_register_duplicate_email_returns_409(client):
    client.post(URL, json=VALID)
    response = client.post(URL, json=VALID)

    assert response.status_code == 409


def test_register_email_is_case_insensitive(client):
    client.post(URL, json=VALID)
    response = client.post(URL, json={**VALID, "email": "USER@example.com"})

    assert response.status_code == 409


def test_register_invalid_email_returns_422(client):
    response = client.post(URL, json={**VALID, "email": "not-an-email"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    "password",
    ["short1!", "alllowercase1!", "ALLUPPERCASE1!", "NoDigitsHere!", "NoSpecial123"],
)
def test_register_weak_password_returns_422(client, password):
    response = client.post(URL, json={**VALID, "password": password})

    assert response.status_code == 422


def test_validate_password_strength_accepts_strong_password():
    assert validate_password_strength("Test1234!") == "Test1234!"