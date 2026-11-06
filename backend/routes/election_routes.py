"""Election and candidate API routes."""
from flask import Blueprint, g, jsonify

from backend.controllers import election_controller, vote_controller
from backend.middleware.auth import admin_required, token_required
from backend.middleware.validation import clean_text, get_json_body

election_bp = Blueprint("elections", __name__, url_prefix="/api/elections")


@election_bp.get("")
@token_required
def list_elections():
    """Admins see every election; voters see open and closed ones."""
    user = g.current_user
    is_admin = user.role == "admin"
    data = election_controller.list_elections(include_drafts=is_admin,
                                              user_id=None if is_admin else user.id)
    return jsonify({"elections": data}), 200


@election_bp.get("/<int:election_id>")
@token_required
def get_election(election_id):
    """Fetch one election with its candidates."""
    election = election_controller.get_election(election_id)
    if election.status == "draft" and g.current_user.role != "admin":
        return jsonify({"error": "Election not found"}), 404
    return jsonify({"election": election.to_dict()}), 200


@election_bp.post("")
@admin_required
def create_election():
    """Create a draft election."""
    election = election_controller.create_election(get_json_body(), g.current_user.id)
    return jsonify({"election": election.to_dict()}), 201


@election_bp.delete("/<int:election_id>")
@admin_required
def delete_election(election_id):
    """Delete a draft election."""
    election_controller.delete_election(election_id, g.current_user.id)
    return jsonify({"message": "Election deleted"}), 200


@election_bp.post("/<int:election_id>/candidates")
@admin_required
def add_candidate(election_id):
    """Add a candidate to a draft election."""
    candidate = election_controller.add_candidate(election_id, get_json_body(),
                                                  g.current_user.id)
    return jsonify({"candidate": candidate.to_dict()}), 201


@election_bp.delete("/<int:election_id>/candidates/<int:candidate_id>")
@admin_required
def remove_candidate(election_id, candidate_id):
    """Remove a candidate from a draft election."""
    election_controller.remove_candidate(election_id, candidate_id, g.current_user.id)
    return jsonify({"message": "Candidate removed"}), 200


@election_bp.patch("/<int:election_id>/status")
@admin_required
def change_status(election_id):
    """Open or close an election."""
    status = clean_text(get_json_body().get("status"), 10, "Status").lower()
    election = election_controller.change_status(election_id, status, g.current_user.id)
    return jsonify({"election": election.to_dict()}), 200


@election_bp.get("/<int:election_id>/results")
@token_required
def results(election_id):
    """Tallied results (public once closed, live for admins)."""
    data = vote_controller.election_results(election_id, g.current_user.role == "admin")
    return jsonify(data), 200
