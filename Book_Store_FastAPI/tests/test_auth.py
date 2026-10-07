"""Auth: register/login, the foundation every other test builds on."""


def test_register_then_login_returns_token(client):
    register = client.post(
        "/api/register",
        json={
            "role": "user",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "phone_no": "9876500000",
            "email": "ada@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    assert register.status_code == 201

    login = client.post("/api/login", json={"email": "ada@example.com", "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"
    assert login.json()["access_token"]


def test_login_with_wrong_password_is_rejected(client):
    client.post(
        "/api/register",
        json={
            "role": "user",
            "first_name": "Grace",
            "last_name": "Hopper",
            "phone_no": "9876500001",
            "email": "grace@example.com",
            "password": "secret123",
            "confirm_password": "secret123",
        },
    )
    login = client.post("/api/login", json={"email": "grace@example.com", "password": "wrong-password"})
    assert login.status_code == 401


def test_duplicate_email_cannot_register_twice(client):
    payload = {
        "role": "user",
        "first_name": "Alan",
        "last_name": "Turing",
        "phone_no": "9876500002",
        "email": "alan@example.com",
        "password": "secret123",
        "confirm_password": "secret123",
    }
    first = client.post("/api/register", json=payload)
    second = client.post("/api/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 401


def test_protected_endpoint_without_token_is_401(client):
    response = client.get("/api/displayAllBooks")
    assert response.status_code == 401
