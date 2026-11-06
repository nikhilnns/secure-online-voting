"""Shared pytest fixtures."""
import pytest
from werkzeug.security import generate_password_hash

from backend.app import create_app
from backend.config import TestConfig
from backend.extensions import db
from backend.middleware.security import limiter
from backend.models import User

VOTER_PASSWORD = "Voter@1234"


@pytest.fixture()
def app():
    """Fresh application with an in-memory database per test."""
    application = create_app(TestConfig)
    limiter.reset()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


def _login(client, email, password):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.get_json()
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


@pytest.fixture()
def admin_headers(client):
    """Authorization header for the bootstrap admin."""
    return _login(client, TestConfig.ADMIN_EMAIL, TestConfig.ADMIN_PASSWORD)


@pytest.fixture()
def make_voter(app, client):
    """Factory creating a voter (approved by default) and returning auth headers."""
    counter = {"n": 0}

    def factory(status="approved"):
        counter["n"] += 1
        n = counter["n"]
        with app.app_context():
            db.session.add(User(full_name=f"Voter {chr(64 + n)}", email=f"voter{n}@test.edu",
                                voter_id=f"1BY23IS{n:03d}", role="voter", status=status,
                                password_hash=generate_password_hash(VOTER_PASSWORD)))
            db.session.commit()
        return _login(client, f"voter{n}@test.edu", VOTER_PASSWORD)

    return factory


@pytest.fixture()
def open_election(client, admin_headers):
    """An open election with three candidates. Returns (election_id, [candidate_ids])."""
    res = client.post("/api/elections", headers=admin_headers,
                      json={"title": "Student Council 2026", "description": "Test"})
    election_id = res.get_json()["election"]["id"]
    cand_ids = []
    for name in ("Alice", "Bob", "Carol"):
        r = client.post(f"/api/elections/{election_id}/candidates", headers=admin_headers,
                        json={"name": name, "affiliation": "Independent"})
        cand_ids.append(r.get_json()["candidate"]["id"])
    client.patch(f"/api/elections/{election_id}/status", headers=admin_headers,
                 json={"status": "open"})
    return election_id, cand_ids
