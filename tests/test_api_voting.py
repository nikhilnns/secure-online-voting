"""API tests: election lifecycle, voting rules, results and integrity."""
from backend.extensions import db
from backend.models import Ballot


def test_admin_creates_election_and_candidates(client, admin_headers):
    res = client.post("/api/elections", headers=admin_headers,
                      json={"title": "CR Election", "description": "ISE 7A"})
    assert res.status_code == 201
    eid = res.get_json()["election"]["id"]
    assert res.get_json()["election"]["status"] == "draft"
    res = client.post(f"/api/elections/{eid}/candidates", headers=admin_headers,
                      json={"name": "Alice"})
    assert res.status_code == 201
    assert res.get_json()["candidate"]["affiliation"] == "Independent"


def test_create_election_missing_title_returns_400(client, admin_headers):
    res = client.post("/api/elections", headers=admin_headers, json={"description": "x"})
    assert res.status_code == 400


def test_cannot_open_with_fewer_than_two_candidates(client, admin_headers):
    eid = client.post("/api/elections", headers=admin_headers,
                      json={"title": "Solo"}).get_json()["election"]["id"]
    client.post(f"/api/elections/{eid}/candidates", headers=admin_headers, json={"name": "Only"})
    res = client.patch(f"/api/elections/{eid}/status", headers=admin_headers,
                       json={"status": "open"})
    assert res.status_code == 409


def test_voter_lists_open_elections_without_drafts(client, admin_headers, make_voter,
                                                   open_election):
    client.post("/api/elections", headers=admin_headers, json={"title": "Hidden draft"})
    res = client.get("/api/elections", headers=make_voter())
    elections = res.get_json()["elections"]
    assert res.status_code == 200
    assert [e["id"] for e in elections] == [open_election[0]]
    assert elections[0]["has_voted"] is False


def test_cast_vote_returns_receipt(client, make_voter, open_election):
    """TC-08: approved voter casts a ballot."""
    eid, cands = open_election
    res = client.post("/api/votes", headers=make_voter(),
                      json={"election_id": eid, "candidate_id": cands[0]})
    assert res.status_code == 201
    assert res.get_json()["receipt"].startswith("VR-")


def test_double_vote_rejected(client, make_voter, open_election):
    """TC-09: one person, one vote."""
    eid, cands = open_election
    headers = make_voter()
    client.post("/api/votes", headers=headers, json={"election_id": eid, "candidate_id": cands[0]})
    res = client.post("/api/votes", headers=headers,
                      json={"election_id": eid, "candidate_id": cands[1]})
    assert res.status_code == 409


def test_pending_voter_cannot_vote(client, make_voter, open_election):
    eid, cands = open_election
    res = client.post("/api/votes", headers=make_voter(status="pending"),
                      json={"election_id": eid, "candidate_id": cands[0]})
    assert res.status_code == 403


def test_admin_cannot_vote(client, admin_headers, open_election):
    eid, cands = open_election
    res = client.post("/api/votes", headers=admin_headers,
                      json={"election_id": eid, "candidate_id": cands[0]})
    assert res.status_code == 403


def test_vote_for_foreign_candidate_rejected(client, admin_headers, make_voter, open_election):
    eid, _ = open_election
    other = client.post("/api/elections", headers=admin_headers,
                        json={"title": "Other"}).get_json()["election"]["id"]
    foreign = client.post(f"/api/elections/{other}/candidates", headers=admin_headers,
                          json={"name": "Mallory"}).get_json()["candidate"]["id"]
    res = client.post("/api/votes", headers=make_voter(),
                      json={"election_id": eid, "candidate_id": foreign})
    assert res.status_code == 400


def test_vote_with_bad_payload_returns_400(client, make_voter, open_election):
    eid, _ = open_election
    headers = make_voter()
    assert client.post("/api/votes", headers=headers,
                       json={"election_id": eid}).status_code == 400
    assert client.post("/api/votes", headers=headers,
                       json={"election_id": "abc", "candidate_id": 1}).status_code == 400
    assert client.post("/api/votes", headers=headers,
                       json={"election_id": True, "candidate_id": 1}).status_code == 400


def test_vote_on_closed_election_rejected(client, admin_headers, make_voter, open_election):
    eid, cands = open_election
    client.patch(f"/api/elections/{eid}/status", headers=admin_headers, json={"status": "closed"})
    res = client.post("/api/votes", headers=make_voter(),
                      json={"election_id": eid, "candidate_id": cands[0]})
    assert res.status_code == 409


def test_status_cannot_go_backwards(client, admin_headers, open_election):
    eid, _ = open_election
    client.patch(f"/api/elections/{eid}/status", headers=admin_headers, json={"status": "closed"})
    res = client.patch(f"/api/elections/{eid}/status", headers=admin_headers,
                       json={"status": "open"})
    assert res.status_code == 409


def test_results_hidden_until_closed_then_correct(client, admin_headers, make_voter,
                                                  open_election):
    """TC-10: results endpoint after closing."""
    eid, cands = open_election
    voters = [make_voter() for _ in range(5)]
    for headers, choice in zip(voters, [0, 0, 1, 0, 2]):
        client.post("/api/votes", headers=headers,
                    json={"election_id": eid, "candidate_id": cands[choice]})
    assert client.get(f"/api/elections/{eid}/results", headers=voters[0]).status_code == 403
    client.patch(f"/api/elections/{eid}/status", headers=admin_headers, json={"status": "closed"})
    res = client.get(f"/api/elections/{eid}/results", headers=voters[0])
    body = res.get_json()
    assert res.status_code == 200
    assert body["total_votes"] == 5
    assert body["winners"] == ["Alice"]
    assert body["results"][0]["votes"] == 3
    assert body["turnout"] == 100.0


def test_receipt_verification(client, make_voter, open_election):
    eid, cands = open_election
    headers = make_voter()
    receipt = client.post("/api/votes", headers=headers,
                          json={"election_id": eid, "candidate_id": cands[1]}).get_json()["receipt"]
    ok = client.post("/api/votes/verify", headers=headers,
                     json={"election_id": eid, "receipt": receipt}).get_json()
    assert ok["found"] is True
    assert "candidate_id" not in ok  # receipt never reveals the choice
    bad = client.post("/api/votes/verify", headers=headers,
                      json={"election_id": eid, "receipt": "VR-0000000000000000"}).get_json()
    assert bad["found"] is False


def test_ballots_are_anonymous(app, client, make_voter, open_election):
    eid, cands = open_election
    client.post("/api/votes", headers=make_voter(),
                json={"election_id": eid, "candidate_id": cands[0]})
    columns = set(Ballot.__table__.columns.keys())
    assert "user_id" not in columns
    with app.app_context():
        assert Ballot.query.count() == 1


def test_integrity_check_detects_tampering(app, client, admin_headers, make_voter,
                                           open_election):
    """TC-11: admin integrity audit catches a modified ballot."""
    eid, cands = open_election
    for choice in (0, 1, 2):
        client.post("/api/votes", headers=make_voter(),
                    json={"election_id": eid, "candidate_id": cands[choice]})
    res = client.get(f"/api/admin/elections/{eid}/verify", headers=admin_headers)
    assert res.get_json()["valid"] is True
    with app.app_context():
        ballot = Ballot.query.filter_by(sequence=2).first()
        ballot.candidate_id = cands[0]
        db.session.commit()
    res = client.get(f"/api/admin/elections/{eid}/verify", headers=admin_headers)
    body = res.get_json()
    assert body["valid"] is False
    assert body["broken_at"] == 2


def test_admin_approves_voter_and_audit_logged(client, admin_headers, make_voter):
    make_voter(status="pending")
    pending = client.get("/api/admin/voters?status=pending",
                         headers=admin_headers).get_json()["voters"]
    assert len(pending) == 1
    res = client.patch(f"/api/admin/voters/{pending[0]['id']}", headers=admin_headers,
                       json={"status": "approved"})
    assert res.get_json()["voter"]["status"] == "approved"
    logs = client.get("/api/admin/audit-logs", headers=admin_headers).get_json()["logs"]
    assert any(log["action"] == "VOTER_APPROVED" for log in logs)
    stats = client.get("/api/admin/stats", headers=admin_headers).get_json()
    assert stats["approved_voters"] == 1


def test_unknown_api_route_returns_json_404(client):
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    assert "error" in res.get_json()
