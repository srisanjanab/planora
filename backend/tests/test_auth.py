USER = {"name": "Asha", "email": "asha@example.com", "password": "strongpass1"}


def register(client, **overrides):
    return client.post("/auth/register", json={**USER, **overrides})


def login(client, email=USER["email"], password=USER["password"]):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_register_success_hides_password(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == USER["email"]
    assert "password" not in body and "password_hash" not in body


def test_duplicate_email_rejected(client):
    register(client)
    r = register(client, email="ASHA@example.com")  # same email, different case
    assert r.status_code == 400


def test_short_password_rejected(client):
    assert register(client, password="short").status_code == 422


def test_login_and_me(client):
    register(client)
    token = login(client).json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Asha"


def test_wrong_password_rejected(client):
    register(client)
    assert login(client, password="wrongpass123").status_code == 401


def test_me_requires_token(client):
    assert client.get("/auth/me").status_code == 401
    r = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
