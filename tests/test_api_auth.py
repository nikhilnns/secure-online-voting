"""API tests: registration, login, JWT protection and lockout."""
from tests.conftest import VOTER_PASSWORD

NEW_VOTER = {"full_name": "Pratyush Kesari A", "email": "pratyush@college.edu",
             "voter_id": "1BY23IS156", "password": "Secure@2026"}


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in res.headers["Content-Security-Policy"]


def test_register_creates_pending_voter(client):
    res = client.post("/api/auth/register", json=NEW_VOTER)
    assert res.status_code == 201
    user = res.get_json()["user"]
    assert user["status"] == "pending"
    assert user["role"] == "voter"
    assert "password_hash" not in user


def test_register_rejects_invalid_email(client):
    res = client.post("/api/auth/register", json={**NEW_VOTER, "email": "bad-email"})
    assert res.status_code == 400
    assert "Invalid email" in res.get_json()["error"]


def test_register_missing_fields_returns_400(client):
    """TC-07: missing required fields -> 400 Bad Request."""
    res = client.post("/api/auth/register", json={"email": "x@y.com"})
    assert res.status_code == 400


def test_register_non_json_body_returns_400(client):
    res = client.post("/api/auth/register", data="not json", content_type="text/plain")
    assert res.status_code == 400


def test_register_duplicate_returns_409(client):
    client.post("/api/auth/register", json=NEW_VOTER)
    res = client.post("/api/auth/register", json={**NEW_VOTER, "email": "other@college.edu"})
    assert res.status_code == 409


def test_login_returns_jwt(client):
    """TC-06: valid credentials -> 200 with token."""
    client.post("/api/auth/register", json=NEW_VOTER)
    res = client.post("/api/auth/login", json={"email": NEW_VOTER["email"],
                                               "password": NEW_VOTER["password"]})
    body = res.get_json()
    assert res.status_code == 200
    assert body["token"].count(".") == 2
    assert body["user"]["email"] == NEW_VOTER["email"]


def test_login_wrong_password_generic_error(client):
    client.post("/api/auth/register", json=NEW_VOTER)
    wrong = client.post("/api/auth/login", json={"email": NEW_VOTER["email"],
                                                 "password": "Wrong@1234"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@college.edu",
                                                   "password": "Wrong@1234"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()["error"] == unknown.get_json()["error"]


def test_account_locks_after_five_failures(client):
    client.post("/api/auth/register", json=NEW_VOTER)
    for _ in range(5):
        client.post("/api/auth/login", json={"email": NEW_VOTER["email"], "password": "Bad@12345"})
    res = client.post("/api/auth/login", json={"email": NEW_VOTER["email"],
                                               "password": NEW_VOTER["password"]})
    assert res.status_code == 423


def test_protected_route_requires_token(client):
    assert client.get("/api/elections").status_code == 401
    bad = client.get("/api/elections", headers={"Authorization": "Bearer abc.def.ghi"})
    assert bad.status_code == 401


def test_voter_cannot_access_admin_routes(client, make_voter):
    headers = make_voter()
    assert client.get("/api/admin/stats", headers=headers).status_code == 403
    res = client.post("/api/elections", headers=headers, json={"title": "Hack"})
    assert res.status_code == 403


def test_me_endpoint(client, make_voter):
    headers = make_voter()
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["user"]["role"] == "voter"
    assert VOTER_PASSWORD not in res.get_data(as_text=True)
