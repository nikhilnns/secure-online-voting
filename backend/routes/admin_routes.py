"""Administrator API routes."""
from flask import Blueprint, g, jsonify, request

from backend.controllers import admin_controller, vote_controller
from backend.middleware.auth import admin_required
from backend.middleware.validation import get_json_body

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.get("/stats")
@admin_required
def stats():
    """Dashboard statistics."""
    return jsonify(admin_controller.dashboard_stats()), 200


@admin_bp.get("/voters")
@admin_required
def voters():
    """List voters, optionally ?status=pending|approved|rejected."""
    return jsonify({"voters": admin_controller.list_voters(request.args.get("status"))}), 200


@admin_bp.patch("/voters/<int:voter_id>")
@admin_required
def decide_voter(voter_id):
    """Approve or reject a voter registration."""
    user = admin_controller.set_voter_status(voter_id, get_json_body().get("status"),
                                             g.current_user.id)
    return jsonify({"voter": user.to_dict()}), 200


@admin_bp.get("/elections/<int:election_id>/verify")
@admin_required
def verify(election_id):
    """Run the ledger integrity check for an election."""
    return jsonify(vote_controller.verify_election_integrity(election_id,
                                                             g.current_user.id)), 200


@admin_bp.get("/audit-logs")
@admin_required
def audit_logs():
    """Recent audit trail entries."""
    limit = request.args.get("limit", default=100, type=int)
    return jsonify({"logs": admin_controller.audit_trail(limit)}), 200
