def reaction_url(movie_id):
    return f"/api/v1/movies/{movie_id}/reaction/"


def counts_url(movie_id):
    return f"/api/v1/movies/{movie_id}/reactions/"


def test_like_movie(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()

    response = client.put(
        reaction_url(movie.id), json={"reaction": "like"}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert response.json() == {"likes": 1, "dislikes": 0}


def test_changing_reaction_replaces_the_old_one(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()
    client.put(reaction_url(movie.id), json={"reaction": "like"}, headers=auth_headers(user))

    response = client.put(
        reaction_url(movie.id), json={"reaction": "dislike"}, headers=auth_headers(user)
    )

    assert response.json() == {"likes": 0, "dislikes": 1}


def test_same_reaction_twice_does_not_double_count(
    client, create_user, create_movie, auth_headers
):
    user = create_user()
    movie = create_movie()
    for _ in range(2):
        response = client.put(
            reaction_url(movie.id), json={"reaction": "like"}, headers=auth_headers(user)
        )

    assert response.json() == {"likes": 1, "dislikes": 0}


def test_reactions_of_different_users_are_counted_together(
    client, create_user, create_movie, auth_headers
):
    first = create_user(email="first@example.com")
    second = create_user(email="second@example.com")
    movie = create_movie()
    client.put(reaction_url(movie.id), json={"reaction": "like"}, headers=auth_headers(first))
    client.put(reaction_url(movie.id), json={"reaction": "dislike"}, headers=auth_headers(second))

    response = client.get(counts_url(movie.id))

    assert response.status_code == 200
    assert response.json() == {"likes": 1, "dislikes": 1}


def test_remove_reaction(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()
    client.put(reaction_url(movie.id), json={"reaction": "like"}, headers=auth_headers(user))

    response = client.delete(reaction_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json() == {"likes": 0, "dislikes": 0}


def test_remove_missing_reaction_returns_404(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()

    response = client.delete(reaction_url(movie.id), headers=auth_headers(user))

    assert response.status_code == 404


def test_invalid_reaction_returns_422(client, create_user, create_movie, auth_headers):
    user = create_user()
    movie = create_movie()

    response = client.put(
        reaction_url(movie.id), json={"reaction": "love"}, headers=auth_headers(user)
    )

    assert response.status_code == 422


def test_reaction_requires_authorization(client, create_movie):
    movie = create_movie()

    response = client.put(reaction_url(movie.id), json={"reaction": "like"})

    assert response.status_code in (401, 403)


def test_reaction_to_unknown_movie_returns_404(client, create_user, auth_headers):
    user = create_user()

    response = client.put(
        reaction_url(9999), json={"reaction": "like"}, headers=auth_headers(user)
    )

    assert response.status_code == 404
    assert client.get(counts_url(9999)).status_code == 404
    