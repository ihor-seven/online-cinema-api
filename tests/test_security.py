import pytest

from src.security import hash_password, validate_password_strength, verify_password

LONG_PASSWORD = "Aa1!" + "x" * 70  # 74 bytes, more than bcrypt allows


def test_password_longer_than_72_bytes_is_rejected():
    with pytest.raises(ValueError):
        validate_password_strength(LONG_PASSWORD)


def test_verify_password_returns_false_for_too_long_password():
    hashed = hash_password("Test1234!")

    assert verify_password("x" * 100, hashed) is False


def test_register_with_too_long_password_returns_422(client):
    response = client.post(
        "/api/v1/accounts/register/",
        json={"email": "user@example.com", "password": LONG_PASSWORD},
    )

    assert response.status_code == 422


def test_login_with_too_long_password_returns_401(client, create_user):
    create_user(email="user@example.com")

    response = client.post(
        "/api/v1/accounts/login/",
        json={"email": "user@example.com", "password": "x" * 100},
    )

    assert response.status_code == 401
