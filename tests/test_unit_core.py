"""Unit tests: vote tallying and the cryptographic ballot ledger."""
from types import SimpleNamespace

from backend.controllers.vote_controller import compute_results
from backend.utils.crypto import (GENESIS_HASH, compute_ballot_hash, generate_receipt,
                                  hash_receipt, verify_chain)

KEY = "unit-test-ledger-key"
CANDIDATES = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}, {"id": 3, "name": "Carol"}]


def test_compute_results_counts_and_percentages():
    """TC-03: core tally returns correct totals, percentages and winner."""
    res = compute_results(CANDIDATES, [1, 1, 2, 1, 3, 2, 1])
    by_name = {r["name"]: r for r in res["results"]}
    assert res["total_votes"] == 7
    assert by_name["Alice"]["votes"] == 4
    assert by_name["Alice"]["percentage"] == 57.14
    assert by_name["Bob"]["votes"] == 2
    assert res["winners"] == ["Alice"]
    assert res["is_tie"] is False
    assert res["results"][0]["name"] == "Alice"  # sorted by votes desc


def test_compute_results_detects_tie():
    res = compute_results(CANDIDATES, [1, 2, 3, 1, 2])
    assert res["is_tie"] is True
    assert set(res["winners"]) == {"Alice", "Bob"}


def test_compute_results_no_votes_and_invalid():
    res = compute_results(CANDIDATES, [99])
    assert res["total_votes"] == 0
    assert res["invalid"] == 1
    assert res["winners"] == []
    assert all(r["percentage"] == 0.0 for r in res["results"])


def test_receipt_hash_is_deterministic_and_normalised():
    receipt = generate_receipt()
    assert receipt.startswith("VR-") and len(receipt) == 19
    assert hash_receipt(receipt) == hash_receipt(" " + receipt.lower() + " ")
    assert hash_receipt(receipt) != receipt


def _build_chain(choices):
    ballots, prev = [], GENESIS_HASH
    for seq, cand in enumerate(choices, start=1):
        r_hash = hash_receipt(f"VR-{seq:016d}")
        b_hash = compute_ballot_hash(KEY, prev, 1, cand, seq, r_hash)
        ballots.append(SimpleNamespace(election_id=1, candidate_id=cand, sequence=seq,
                                       receipt_hash=r_hash, prev_hash=prev,
                                       ballot_hash=b_hash))
        prev = b_hash
    return ballots


def test_hash_chain_valid():
    """TC-04: an untouched ledger verifies successfully."""
    assert verify_chain(KEY, _build_chain([1, 2, 1, 3]))["valid"] is True


def test_hash_chain_detects_tampered_vote():
    """TC-05: changing a stored vote breaks the chain."""
    ballots = _build_chain([1, 2, 1, 3])
    ballots[1].candidate_id = 1  # attacker flips Bob -> Alice
    result = verify_chain(KEY, ballots)
    assert result["valid"] is False
    assert result["broken_at"] == 2


def test_hash_chain_detects_deleted_ballot():
    ballots = _build_chain([1, 2, 1, 3])
    del ballots[1]
    assert verify_chain(KEY, ballots)["valid"] is False


def test_hash_chain_requires_secret_key():
    """Recomputing hashes with the wrong key fails verification."""
    assert verify_chain("wrong-key", _build_chain([1, 2]))["valid"] is False
