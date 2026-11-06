"""Cryptographic helpers for the ballot ledger and vote receipts."""
import hashlib
import hmac
import secrets

GENESIS_HASH = "0" * 64


def generate_receipt() -> str:
    """Return a random, URL-safe receipt code shown to the voter exactly once."""
    return "VR-" + secrets.token_hex(8).upper()


def hash_receipt(receipt: str) -> str:
    """One-way hash of a receipt; only this hash is stored in the database."""
    return hashlib.sha256(receipt.strip().upper().encode("utf-8")).hexdigest()


def compute_ballot_hash(key: str, prev_hash: str, election_id: int, candidate_id: int,
                        sequence: int, receipt_hash: str) -> str:
    """HMAC-SHA256 over the ballot contents chained to the previous ballot hash.

    Using an HMAC (not a bare SHA-256) means an attacker with database write
    access cannot recompute a valid chain after tampering without the server key.
    """
    message = f"{prev_hash}|{election_id}|{candidate_id}|{sequence}|{receipt_hash}"
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_chain(key: str, ballots) -> dict:
    """Recompute the hash chain for an ordered list of ballots.

    Returns a dict with ``valid`` and, when invalid, the first broken sequence.
    """
    prev = GENESIS_HASH
    for expected_seq, ballot in enumerate(ballots, start=1):
        if ballot.sequence != expected_seq:
            return {"valid": False, "broken_at": expected_seq, "reason": "sequence gap"}
        if ballot.prev_hash != prev:
            return {"valid": False, "broken_at": ballot.sequence, "reason": "prev_hash mismatch"}
        recomputed = compute_ballot_hash(key, prev, ballot.election_id, ballot.candidate_id,
                                         ballot.sequence, ballot.receipt_hash)
        if not hmac.compare_digest(recomputed, ballot.ballot_hash):
            return {"valid": False, "broken_at": ballot.sequence, "reason": "hash mismatch"}
        prev = ballot.ballot_hash
    return {"valid": True, "broken_at": None, "reason": None, "head_hash": prev}
