"""Administrator workflows: voter approval, dashboard statistics and audit trail."""
from backend.extensions import db
from backend.models import AuditLog, Ballot, Election, User
from backend.utils.audit import log_action
from backend.utils.errors import ServiceError

VALID_DECISIONS = {"approved", "rejected"}


def list_voters(status=None) -> list:
    """List voter accounts, optionally filtered by status."""
    query = User.query.filter_by(role="voter")
    if status:
        if status not in {"pending", "approved", "rejected"}:
            raise ServiceError("Invalid status filter")
        query = query.filter_by(status=status)
    return [u.to_dict() for u in query.order_by(User.created_at.desc()).all()]


def set_voter_status(voter_id: int, decision: str, admin_id: int) -> User:
    """Approve or reject a voter registration."""
    if decision not in VALID_DECISIONS:
        raise ServiceError("Status must be 'approved' or 'rejected'")
    user = db.session.get(User, voter_id)
    if user is None or user.role != "voter":
        raise ServiceError("Voter not found", 404)
    user.status = decision
    log_action(f"VOTER_{decision.upper()}", admin_id, f"Voter {user.voter_id}")
    db.session.commit()
    return user


def dashboard_stats() -> dict:
    """Headline numbers for the admin dashboard."""
    voters = User.query.filter_by(role="voter")
    return {
        "total_voters": voters.count(),
        "approved_voters": voters.filter_by(status="approved").count(),
        "pending_voters": User.query.filter_by(role="voter", status="pending").count(),
        "elections": Election.query.count(),
        "open_elections": Election.query.filter_by(status="open").count(),
        "ballots_cast": Ballot.query.count(),
    }


def audit_trail(limit: int = 100) -> list:
    """Most recent audit log entries."""
    limit = max(1, min(limit, 500))
    rows = AuditLog.query.order_by(AuditLog.id.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]
