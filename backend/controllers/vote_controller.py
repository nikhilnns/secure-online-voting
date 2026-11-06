"""Core voting logic: casting ballots, tallying results and verifying integrity."""
from flask import current_app
from sqlalchemy.exc import IntegrityError

from backend.controllers.election_controller import get_election
from backend.extensions import db
from backend.models import Ballot, Candidate, User, VoteRecord
from backend.utils.audit import log_action
from backend.utils.crypto import (GENESIS_HASH, compute_ballot_hash, generate_receipt,
                                  hash_receipt, verify_chain)
from backend.utils.errors import ServiceError


def cast_vote(user: User, election_id: int, candidate_id: int) -> dict:
    """Cast one anonymous ballot for an eligible voter.

    Rules enforced:
      * only approved voters (not admins) may vote;
      * the election must be open;
      * the candidate must belong to the election;
      * one vote per voter per election (checked here and by a DB constraint).
    The participation record and the anonymous ballot are written atomically.
    """
    if user.role != "voter":
        raise ServiceError("Administrators cannot vote", 403)
    if user.status != "approved":
        raise ServiceError("Your account has not been approved to vote yet", 403)

    election = get_election(election_id)
    if election.status != "open":
        raise ServiceError("This election is not open for voting", 409)

    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None or candidate.election_id != election.id:
        raise ServiceError("Invalid candidate for this election", 400)

    if VoteRecord.query.filter_by(election_id=election.id, user_id=user.id).first():
        raise ServiceError("You have already voted in this election", 409)

    receipt = generate_receipt()
    receipt_hash = hash_receipt(receipt)
    last = (Ballot.query.filter_by(election_id=election.id)
            .order_by(Ballot.sequence.desc()).first())
    prev_hash = last.ballot_hash if last else GENESIS_HASH
    sequence = last.sequence + 1 if last else 1
    ballot_hash = compute_ballot_hash(current_app.config["LEDGER_KEY"], prev_hash, election.id,
                                      candidate.id, sequence, receipt_hash)
    try:
        db.session.add(VoteRecord(election_id=election.id, user_id=user.id))
        db.session.add(Ballot(election_id=election.id, candidate_id=candidate.id,
                              sequence=sequence, receipt_hash=receipt_hash,
                              prev_hash=prev_hash, ballot_hash=ballot_hash))
        log_action("VOTE_CAST", user.id, f"Voted in election #{election.id}")
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ServiceError("You have already voted in this election", 409) from exc

    return {"message": "Vote cast successfully", "receipt": receipt, "election_id": election.id}


def verify_receipt(election_id: int, receipt: str) -> dict:
    """Let a voter confirm that their ballot is in the ledger.

    The candidate is deliberately NOT revealed, so a receipt cannot be used to
    prove to a third party how someone voted (prevents vote buying/coercion).
    """
    if not isinstance(receipt, str) or not receipt.strip():
        raise ServiceError("Receipt code is required")
    get_election(election_id)
    ballot = Ballot.query.filter_by(election_id=election_id,
                                    receipt_hash=hash_receipt(receipt)).first()
    if ballot is None:
        return {"found": False, "message": "No ballot matches this receipt"}
    return {"found": True, "sequence": ballot.sequence, "ballot_hash": ballot.ballot_hash,
            "message": "Your ballot is recorded in the tamper-evident ledger"}


def compute_results(candidates: list, ballots: list) -> dict:
    """Pure tally function: count ballots per candidate, percentages and winners.

    ``candidates`` is a list of dicts with ``id`` and ``name``; ``ballots`` is a
    list of candidate ids. Ties produce several winners. Votes for unknown
    candidates are ignored and reported as ``invalid``.
    """
    counts = {c["id"]: 0 for c in candidates}
    invalid = 0
    for candidate_id in ballots:
        if candidate_id in counts:
            counts[candidate_id] += 1
        else:
            invalid += 1
    total = sum(counts.values())
    rows = []
    for cand in candidates:
        votes = counts[cand["id"]]
        pct = round(votes * 100.0 / total, 2) if total else 0.0
        rows.append({**cand, "votes": votes, "percentage": pct})
    rows.sort(key=lambda r: (-r["votes"], r["name"]))
    top = rows[0]["votes"] if rows else 0
    winners = [r["name"] for r in rows if r["votes"] == top] if total else []
    return {"total_votes": total, "invalid": invalid, "results": rows, "winners": winners,
            "is_tie": len(winners) > 1}


def election_results(election_id: int, is_admin: bool) -> dict:
    """Results are public after closing; admins may view a live tally."""
    election = get_election(election_id)
    if election.status != "closed" and not is_admin:
        raise ServiceError("Results are published after the election closes", 403)
    candidates = [{"id": c.id, "name": c.name, "affiliation": c.affiliation}
                  for c in election.candidates]
    ballots = [b.candidate_id for b in Ballot.query.filter_by(election_id=election.id).all()]
    data = compute_results(candidates, ballots)
    eligible = User.query.filter_by(role="voter", status="approved").count()
    data["eligible_voters"] = eligible
    data["turnout"] = round(data["total_votes"] * 100.0 / eligible, 2) if eligible else 0.0
    data["election"] = election.to_dict(include_candidates=False)
    return data


def verify_election_integrity(election_id: int, admin_id: int) -> dict:
    """Recompute the ballot hash chain and cross-check it with participation records."""
    election = get_election(election_id)
    ballots = (Ballot.query.filter_by(election_id=election.id)
               .order_by(Ballot.sequence.asc()).all())
    chain = verify_chain(current_app.config["LEDGER_KEY"], ballots)
    records = VoteRecord.query.filter_by(election_id=election.id).count()
    counts_match = records == len(ballots)
    result = {"election_id": election.id, "ballots": len(ballots), "vote_records": records,
              "counts_match": counts_match, "chain_valid": chain["valid"],
              "broken_at": chain["broken_at"], "reason": chain["reason"],
              "head_hash": chain.get("head_hash"),
              "valid": chain["valid"] and counts_match}
    log_action("INTEGRITY_CHECK", admin_id,
               f"Election #{election.id}: {'PASS' if result['valid'] else 'FAIL'}")
    db.session.commit()
    return result
