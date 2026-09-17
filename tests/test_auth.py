def test_register_ok(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "bob@example.com", "password": "password123", "name": "Bob"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "bob@example.com"


def test_register_duplicate_email_is_409(client):
    client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "name": "Dup"},
    )
    r = client.post(
        "/api/auth/register",
        json={"email": "dup@example.com", "password": "password123", "name": "Dup2"},
    )
    assert r.status_code == 409


def test_register_weak_password_is_422(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "c@example.com", "password": "short", "name": "C"},
    )
    assert r.status_code == 422


def test_register_invalid_email_is_422(client):
    r = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password123", "name": "D"},
    )
    assert r.status_code == 422


def test_login_ok(client):
    client.post("/api/auth/register",
                json={"email": "logintest@example.com", "password": "password123",
                      "name": "Login"})
    r = client.post(
        "/api/auth/login", json={"email": "logintest@example.com", "password": "password123"}
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password_is_401(client, user_headers):
    r = client.post(
        "/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"}
    )
    assert r.status_code == 401


def test_login_unknown_user_is_401(client):
    r = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "whatever123"}
    )
    assert r.status_code == 401


def test_me_without_token_is_401(client):
    r = client.get("/api/auth/me")
    assert r.status_code in (401, 403)


def test_me_with_token_ok(client, user_headers):
    r = client.get("/api/auth/me", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["id"] > 0
    assert r.json()["name"] == "Test User"


def test_me_with_garbage_token_is_401(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401