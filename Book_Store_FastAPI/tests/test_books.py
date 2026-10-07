"""Books: role guards (admin-only writes) + the Redis-cached read path."""


def _create_book(client, admin_headers, name="Dune", genre="Sci-Fi"):
    return client.post(
        "/api/addingBook",
        headers=admin_headers,
        json={
            "name": name,
            "description": "A desert planet epic.",
            "author": "Frank Herbert",
            "image": "/static/book-covers/dune.jpg",
            "Price": 499.0,
            "quantity": 10,
            "genre": genre,
        },
    )


def test_admin_can_create_a_book(client, admin_headers):
    response = _create_book(client, admin_headers)
    assert response.status_code == 201
    body = response.json()["book"]
    assert body["name"] == "Dune"
    assert body["genre"] == "Sci-Fi"


def test_non_admin_cannot_create_a_book(client, user_headers):
    response = _create_book(client, user_headers, name="Not Allowed")
    assert response.status_code == 403


def test_created_book_is_visible_and_cacheable(client, admin_headers, user_headers):
    _create_book(client, admin_headers, name="Foundation")

    # First read: cache miss, served from the database.
    first = client.get("/api/displayAllBooks", headers=user_headers)
    assert first.status_code == 200
    assert any(b["name"] == "Foundation" for b in first.json()["books"])

    # Second read: cache-aside behaviour is transparent — same data either way,
    # whether or not a Redis server happens to be running locally.
    second = client.get("/api/displayAllBooks", headers=user_headers)
    assert second.status_code == 200
    assert first.json()["books"] == second.json()["books"]


def test_search_book_by_keyword(client, admin_headers, user_headers):
    _create_book(client, admin_headers, name="The Hobbit", genre="Fantasy")
    response = client.post(
        "/api/searchBookByKeyword", headers=user_headers, json={"search": "Hobbit"}
    )
    assert response.status_code == 200
    assert any(b["name"] == "The Hobbit" for b in response.json()["books"])
