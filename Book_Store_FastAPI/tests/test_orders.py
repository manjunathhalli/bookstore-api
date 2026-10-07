"""Orders: the end-to-end path — book, address, then place an order."""


def _create_book(client, admin_headers, name="1984", price=250.0, quantity=5):
    return client.post(
        "/api/addingBook",
        headers=admin_headers,
        json={
            "name": name,
            "description": "A dystopian classic.",
            "author": "George Orwell",
            "image": "/static/book-covers/1984.jpg",
            "Price": price,
            "quantity": quantity,
        },
    )


def _add_address(client, user_headers):
    client.post(
        "/api/addAddress",
        headers=user_headers,
        json={
            "address": "221B Baker Street",
            "city": "London",
            "state": "London",
            "landmark": "Near the park",
            "pincode": 100001,
            "address_type": "home",
        },
    )
    addresses = client.post("/api/getAddress", headers=user_headers).json()["addresses"]
    return addresses[0]["id"]


def test_place_order_reduces_stock_and_records_total(client, admin_headers, user_headers):
    _create_book(client, admin_headers, name="1984", price=250.0, quantity=5)
    address_id = _add_address(client, user_headers)

    response = client.post(
        "/api/placeOrder",
        headers=user_headers,
        json={"name": "1984", "address_id": address_id, "quantity": 2},
    )
    assert response.status_code == 201
    assert response.json()["total_price"] == 500.0

    books = client.get("/api/displayAllBooks", headers=user_headers).json()["books"]
    book = next(b for b in books if b["name"] == "1984")
    assert book["quantity"] == 3  # 5 - 2


def test_cannot_order_more_than_available_stock(client, admin_headers, user_headers):
    _create_book(client, admin_headers, name="Scarce Book", quantity=1)
    address_id = _add_address(client, user_headers)

    response = client.post(
        "/api/placeOrder",
        headers=user_headers,
        json={"name": "Scarce Book", "address_id": address_id, "quantity": 5},
    )
    assert response.status_code == 400


def test_cannot_use_another_users_address(client, admin_headers, user_headers):
    from tests.conftest import register_and_login

    _create_book(client, admin_headers, name="Shared Book", quantity=5)
    address_id = _add_address(client, user_headers)

    other_headers = register_and_login(client, "user", "other-shopper@example.com")
    response = client.post(
        "/api/placeOrder",
        headers=other_headers,
        json={"name": "Shared Book", "address_id": address_id, "quantity": 1},
    )
    assert response.status_code == 404
