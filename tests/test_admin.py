from sqlalchemy import select

from src.models import ActivationToken, User, UserGroupEnum


def group_url(user_id):
    return f"/api/v1/admin/users/{user_id}/group/"


def activate_url(user_id):
    return f"/api/v1/admin/users/{user_id}/activate/"


def test_admin_can_change_user_group(client, db_session, create_user, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    target = create_user(email="target@example.com")

    response = client.patch(
        group_url(target.id),
        json={"group": "MODERATOR"},
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["group"] == "MODERATOR"
    db_session.expire_all()
    updated = db_session.scalar(select(User).where(User.id == target.id))
    assert updated.group.name == UserGroupEnum.MODERATOR


def test_moderator_cannot_change_group(client, create_user, auth_headers):
    moderator = create_user(email="mod@example.com", group=UserGroupEnum.MODERATOR)
    target = create_user(email="target@example.com")

    response = client.patch(
        group_url(target.id),
        json={"group": "ADMIN"},
        headers=auth_headers(moderator),
    )

    assert response.status_code == 403


def test_regular_user_cannot_change_group(client, create_user, auth_headers):
    user = create_user(email="user@example.com")
    target = create_user(email="target@example.com")

    response = client.patch(
        group_url(target.id), json={"group": "ADMIN"}, headers=auth_headers(user)
    )

    assert response.status_code == 403


def test_admin_endpoints_require_authorization(client):
    response = client.patch(group_url(1), json={"group": "ADMIN"})

    assert response.status_code in (401, 403)


def test_change_group_unknown_user_returns_404(client, create_user, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)

    response = client.patch(
        group_url(9999), json={"group": "MODERATOR"}, headers=auth_headers(admin)
    )

    assert response.status_code == 404


def test_change_group_invalid_group_returns_422(client, create_user, auth_headers):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    target = create_user(email="target@example.com")

    response = client.patch(
        group_url(target.id), json={"group": "KING"}, headers=auth_headers(admin)
    )

    assert response.status_code == 422


def test_admin_can_activate_user_manually(
    client, db_session, create_user, auth_headers
):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    target = create_user(email="target@example.com", is_active=False)

    response = client.post(activate_url(target.id), headers=auth_headers(admin))

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    db_session.expire_all()
    assert db_session.scalar(select(User).where(User.id == target.id)).is_active


def test_admin_activation_removes_pending_token(
    client, db_session, create_user, auth_headers
):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    client.post(
        "/api/v1/accounts/register/",
        json={"email": "new@example.com", "password": "Test1234!"},
    )
    db_session.expire_all()
    target = db_session.scalar(select(User).where(User.email == "new@example.com"))
    assert db_session.scalar(select(ActivationToken)) is not None

    client.post(activate_url(target.id), headers=auth_headers(admin))

    db_session.expire_all()
    assert db_session.scalar(select(ActivationToken)) is None


def test_moderator_cannot_activate_user(client, create_user, auth_headers):
    moderator = create_user(email="mod@example.com", group=UserGroupEnum.MODERATOR)
    target = create_user(email="target@example.com", is_active=False)

    response = client.post(activate_url(target.id), headers=auth_headers(moderator))

    assert response.status_code == 403