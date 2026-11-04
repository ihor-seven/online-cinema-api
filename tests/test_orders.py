from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.models import Order, OrderItem, OrderStatusEnum, UserGroupEnum

CART_ITEMS = "/api/v1/cart/items/"
ORDERS = "/api/v1/orders/"
PURCHASED = "/api/v1/purchased/"
ADMIN_ORDERS = "/api/v1/admin/orders/"


def make_order(db_session, user, movies, status=OrderStatusEnum.PENDING):
    order = Order(
        user_id=user.id,
        status=status,
        total_amount=sum((m.price for m in movies), Decimal("0.00")),
    )
    order.items = [OrderItem(movie_id=m.id, price_at_order=m.price) for m in movies]
    db_session.add(order)
    db_session.commit()
    return order


def add_to_cart(client, user, auth_headers, *movies):
    for movie in movies:
        response = client.post(
            CART_ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user)
        )
        assert response.status_code == 201


def order_url(order_id, suffix=""):
    return f"{ORDERS}{order_id}/{suffix}"


# ---------- create ----------


def test_create_order_from_cart(client, create_user, create_movie, auth_headers):
    user = create_user()
    first = create_movie(name="First", price="9.99")
    second = create_movie(name="Second", price="12.00")
    add_to_cart(client, user, auth_headers, first, second)

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 201
    data = response.json()
    assert data["excluded"] == []
    order = data["order"]
    assert order["status"] == "pending"
    assert float(order["total_amount"]) == pytest.approx(21.99)
    assert [i["movie_name"] for i in order["items"]] == ["First", "Second"]
    assert float(order["items"][0]["price_at_order"]) == pytest.approx(9.99)


def test_create_order_with_empty_cart_returns_400(client, create_user, auth_headers):
    user = create_user()

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 400


def test_order_requires_authorization(client):
    assert client.post(ORDERS).status_code in (401, 403)
    assert client.get(ORDERS).status_code in (401, 403)


def test_order_keeps_price_at_order_time(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie(price="9.99")
    add_to_cart(client, user, auth_headers, movie)
    order_id = client.post(ORDERS, headers=auth_headers(user)).json()["order"]["id"]

    movie.price = Decimal("20.00")
    db_session.commit()

    response = client.get(order_url(order_id), headers=auth_headers(user))
    assert float(response.json()["items"][0]["price_at_order"]) == pytest.approx(9.99)


def test_purchased_movies_are_excluded_from_order(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    bought = create_movie(name="Bought")
    new = create_movie(name="New")
    add_to_cart(client, user, auth_headers, bought, new)
    make_order(db_session, user, [bought], OrderStatusEnum.PAID)

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 201
    data = response.json()
    assert [i["movie_name"] for i in data["order"]["items"]] == ["New"]
    assert data["excluded"] == [
        {"movie_id": bought.id, "name": "Bought", "reason": "already_purchased"}
    ]


def test_order_fails_when_all_movies_are_purchased(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    bought = create_movie()
    add_to_cart(client, user, auth_headers, bought)
    make_order(db_session, user, [bought], OrderStatusEnum.PAID)

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["excluded"][0]["reason"] == "already_purchased"
    assert client.get(ORDERS, headers=auth_headers(user)).json()["total_items"] == 1


def test_movies_in_pending_order_cannot_be_ordered_again(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()
    add_to_cart(client, user, auth_headers, movie)
    client.post(ORDERS, headers=auth_headers(user))

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 400
    assert response.json()["detail"]["excluded"][0]["reason"] == "pending_order"


def test_can_order_again_after_cancel(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()
    add_to_cart(client, user, auth_headers, movie)
    order_id = client.post(ORDERS, headers=auth_headers(user)).json()["order"]["id"]
    client.post(order_url(order_id, "cancel/"), headers=auth_headers(user))

    response = client.post(ORDERS, headers=auth_headers(user))

    assert response.status_code == 201


def test_cannot_add_purchased_movie_to_cart(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()
    make_order(db_session, user, [movie], OrderStatusEnum.PAID)

    response = client.post(
        CART_ITEMS, json={"movie_id": movie.id}, headers=auth_headers(user)
    )

    assert response.status_code == 409


# ---------- list and details ----------


def test_list_shows_only_own_orders_newest_first(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user(email="user@example.com")
    other = create_user(email="other@example.com")
    movie = create_movie()
    first = make_order(db_session, user, [movie])
    second = make_order(db_session, user, [movie], OrderStatusEnum.CANCELED)
    make_order(db_session, other, [movie])

    response = client.get(ORDERS, headers=auth_headers(user))

    data = response.json()
    assert data["total_items"] == 2
    assert [o["id"] for o in data["items"]] == [second.id, first.id]


def test_list_filter_by_status_and_pagination(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()
    make_order(db_session, user, [movie], OrderStatusEnum.PAID)
    make_order(db_session, user, [movie], OrderStatusEnum.CANCELED)
    make_order(db_session, user, [movie], OrderStatusEnum.CANCELED)
    headers = auth_headers(user)

    canceled = client.get(ORDERS, params={"status": "canceled"}, headers=headers).json()
    paged = client.get(ORDERS, params={"per_page": 2}, headers=headers).json()

    assert canceled["total_items"] == 2
    assert paged["total_pages"] == 2
    assert len(paged["items"]) == 2


def test_list_with_invalid_status_returns_422(client, create_user, auth_headers):
    user = create_user()

    response = client.get(ORDERS, params={"status": "weird"}, headers=auth_headers(user))

    assert response.status_code == 422


def test_get_own_order(client, db_session, create_user, create_movie, auth_headers):
    user = create_user()
    order = make_order(db_session, user, [create_movie(name="Inception")])

    response = client.get(order_url(order.id), headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["items"][0]["movie_name"] == "Inception"


def test_cannot_get_someone_elses_order(
    client, db_session, create_user, create_movie, auth_headers
):
    owner = create_user(email="owner@example.com")
    other = create_user(email="other@example.com")
    order = make_order(db_session, owner, [create_movie()])

    response = client.get(order_url(order.id), headers=auth_headers(other))

    assert response.status_code == 404


# ---------- cancel ----------


def test_cancel_pending_order(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    order = make_order(db_session, user, [create_movie()])

    response = client.post(order_url(order.id, "cancel/"), headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_cannot_cancel_paid_order(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    order = make_order(db_session, user, [create_movie()], OrderStatusEnum.PAID)

    response = client.post(order_url(order.id, "cancel/"), headers=auth_headers(user))

    assert response.status_code == 400
    assert "refund" in response.json()["detail"]


def test_cannot_cancel_order_twice(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    order = make_order(db_session, user, [create_movie()], OrderStatusEnum.CANCELED)

    response = client.post(order_url(order.id, "cancel/"), headers=auth_headers(user))

    assert response.status_code == 400


def test_cannot_cancel_someone_elses_order(
    client, db_session, create_user, create_movie, auth_headers
):
    owner = create_user(email="owner@example.com")
    other = create_user(email="other@example.com")
    order = make_order(db_session, owner, [create_movie()])

    response = client.post(order_url(order.id, "cancel/"), headers=auth_headers(other))

    assert response.status_code == 404


# ---------- purchased ----------


def test_purchased_list_contains_only_paid_movies(
    client, db_session, create_user, create_movie, auth_headers
):
    user = create_user()
    paid = create_movie(name="Paid")
    pending = create_movie(name="Pending")
    canceled = create_movie(name="Canceled")
    make_order(db_session, user, [paid], OrderStatusEnum.PAID)
    make_order(db_session, user, [pending], OrderStatusEnum.PENDING)
    make_order(db_session, user, [canceled], OrderStatusEnum.CANCELED)

    response = client.get(PURCHASED, headers=auth_headers(user))

    assert [m["name"] for m in response.json()["items"]] == ["Paid"]


def test_purchased_requires_authorization(client):
    assert client.get(PURCHASED).status_code in (401, 403)


# ---------- admin ----------


@pytest.fixture
def admin_setup(db_session, create_user, create_movie):
    admin = create_user(email="admin@example.com", group=UserGroupEnum.ADMIN)
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")
    movie = create_movie()
    return {
        "admin": admin,
        "first": first,
        "second": second,
        "paid": make_order(db_session, first, [movie], OrderStatusEnum.PAID),
        "pending": make_order(db_session, second, [movie], OrderStatusEnum.PENDING),
    }


def test_admin_sees_orders_of_all_users(client, auth_headers, admin_setup):
    response = client.get(ADMIN_ORDERS, headers=auth_headers(admin_setup["admin"]))

    assert response.status_code == 200
    assert response.json()["total_items"] == 2


def test_admin_filters_orders_by_user_and_status(client, auth_headers, admin_setup):
    headers = auth_headers(admin_setup["admin"])

    by_user = client.get(ADMIN_ORDERS, params={"user_id": admin_setup["first"].id}, headers=headers)
    by_status = client.get(ADMIN_ORDERS, params={"status": "pending"}, headers=headers)

    assert [o["id"] for o in by_user.json()["items"]] == [admin_setup["paid"].id]
    assert [o["id"] for o in by_status.json()["items"]] == [admin_setup["pending"].id]


def test_admin_filters_orders_by_date(client, auth_headers, admin_setup):
    headers = auth_headers(admin_setup["admin"])
    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)

    today_only = client.get(
        ADMIN_ORDERS, params={"date_from": str(today), "date_to": str(today)}, headers=headers
    )
    future = client.get(ADMIN_ORDERS, params={"date_from": str(tomorrow)}, headers=headers)

    assert today_only.json()["total_items"] == 2
    assert future.json()["total_items"] == 0


def test_regular_user_cannot_use_admin_orders(client, auth_headers, admin_setup):
    response = client.get(ADMIN_ORDERS, headers=auth_headers(admin_setup["first"]))

    assert response.status_code == 403
    