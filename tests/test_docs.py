import pytest

DOCS_URLS = ["/docs", "/redoc", "/openapi.json"]
EMAIL = "user@example.com"
PASSWORD = "Test1234!"


@pytest.mark.parametrize("url", DOCS_URLS)
def test_docs_require_credentials(client, url):
    response = client.get(url)

    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic")


@pytest.mark.parametrize("url", DOCS_URLS)
def test_docs_reject_wrong_password(client, create_user, url):
    create_user(email=EMAIL, password=PASSWORD)

    response = client.get(url, auth=(EMAIL, "Wrong1234!"))

    assert response.status_code == 401


@pytest.mark.parametrize("url", DOCS_URLS)
def test_docs_reject_unknown_user(client, url):
    response = client.get(url, auth=("nobody@example.com", PASSWORD))

    assert response.status_code == 401


def test_docs_reject_inactive_user(client, create_user):
    create_user(email=EMAIL, password=PASSWORD, is_active=False)

    response = client.get("/docs", auth=(EMAIL, PASSWORD))

    assert response.status_code == 401


def test_docs_reject_too_long_password_without_error(client, create_user):
    create_user(email=EMAIL, password=PASSWORD)

    response = client.get("/docs", auth=(EMAIL, "x" * 100))

    assert response.status_code == 401


def test_swagger_ui_is_available_for_active_user(client, create_user):
    create_user(email=EMAIL, password=PASSWORD)

    response = client.get("/docs", auth=(EMAIL, PASSWORD))

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "swagger-ui" in response.text


def test_redoc_is_available_for_active_user(client, create_user):
    create_user(email=EMAIL, password=PASSWORD)

    response = client.get("/redoc", auth=(EMAIL, PASSWORD))

    assert response.status_code == 200
    assert "redoc" in response.text.lower()


def test_openapi_schema_is_available_for_active_user(client, create_user):
    create_user(email=EMAIL, password=PASSWORD)

    response = client.get("/openapi.json", auth=(EMAIL, PASSWORD))

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/accounts/register/" in schema["paths"]
    assert "/docs" not in schema["paths"]


def test_health_endpoint_stays_public(client):
    response = client.get("/health")

    assert response.status_code == 200
