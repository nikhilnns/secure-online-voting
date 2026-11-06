"""Voting API routes."""
from flask import Blueprint, g, jsonify

from backend.controllers import vote_controller
from backend.middleware.auth import token_required
from backend.middleware.validation import get_json_body, require_int

vote_bp = Blueprint("votes", __name__, url_prefix="/api/votes")


@vote_bp.post("")
@token_required
def cast_vote():
    """Cast a ballot and receive a one-time verification receipt."""
    data = get_json_body()
    election_id = require_int(data.get("election_id"), "election_id")
    candidate_id = require_int(data.get("candidate_id"), "candidate_id")
    result = vote_controller.cast_vote(g.current_user, election_id, candidate_id)
    return jsonify(result), 201


@vote_bp.post("/verify")
@token_required
def verify_receipt():
    """Confirm that a receipt's ballot exists in the ledger."""
    data = get_json_body()
    election_id = require_int(data.get("election_id"), "election_id")
    return jsonify(vote_controller.verify_receipt(election_id, data.get("receipt"))), 200
