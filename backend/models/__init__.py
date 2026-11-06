"""ORM models for the Secure Online Voting Management System."""
from datetime import datetime, timezone

from backend.extensions import db


def utcnow():
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


class User(db.Model):  # pylint: disable=too-few-public-methods
    """A registered person: either an administrator or a voter."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    voter_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="voter")  # admin | voter
    # status: pending | approved | rejected
    status = db.Column(db.String(10), nullable=False, default="pending")
    failed_logins = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        """Public representation (never exposes the password hash)."""
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "voter_id": self.voter_id,
            "role": self.role,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Election(db.Model):  # pylint: disable=too-few-public-methods
    """An election moves through the lifecycle draft -> open -> closed."""

    __tablename__ = "elections"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(1000), nullable=False, default="")
    status = db.Column(db.String(10), nullable=False, default="draft")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    opened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    candidates = db.relationship(
        "Candidate", backref="election", cascade="all, delete-orphan", order_by="Candidate.id"
    )

    def to_dict(self, include_candidates=True):
        """Serialize the election."""
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }
        if include_candidates:
            data["candidates"] = [c.to_dict() for c in self.candidates]
        return data


class Candidate(db.Model):  # pylint: disable=too-few-public-methods
    """A candidate standing in a particular election."""

    __tablename__ = "candidates"

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey("elections.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    affiliation = db.Column(db.String(120), nullable=False, default="Independent")
    manifesto = db.Column(db.String(500), nullable=False, default="")

    def to_dict(self):
        """Serialize the candidate."""
        return {
            "id": self.id,
            "election_id": self.election_id,
            "name": self.name,
            "affiliation": self.affiliation,
            "manifesto": self.manifesto,
        }


class VoteRecord(db.Model):  # pylint: disable=too-few-public-methods
    """Records THAT a voter has voted in an election - never WHO they voted for.

    The unique constraint is the database-level guarantee of one-person-one-vote,
    which also protects against race conditions from concurrent requests.
    """

    __tablename__ = "vote_records"
    __table_args__ = (db.UniqueConstraint("election_id", "user_id", name="uq_one_vote"),)

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey("elections.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    voted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class Ballot(db.Model):  # pylint: disable=too-few-public-methods
    """An anonymous ballot stored in a tamper-evident HMAC hash chain.

    A ballot carries no user reference and no timestamp, so it cannot be linked
    back to a voter. Each ballot's hash covers the previous ballot's hash, so any
    edit, insertion or deletion breaks the chain and is detected on verification.
    """

    __tablename__ = "ballots"
    __table_args__ = (db.UniqueConstraint("election_id", "sequence", name="uq_ballot_seq"),)

    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey("elections.id"), nullable=False, index=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidates.id"), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    receipt_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    prev_hash = db.Column(db.String(64), nullable=False)
    ballot_hash = db.Column(db.String(64), nullable=False)


class AuditLog(db.Model):  # pylint: disable=too-few-public-methods
    """Append-only log of security-relevant actions."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.String(500), nullable=False, default="")
    ip_address = db.Column(db.String(45), nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        """Serialize the log entry."""
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "action": self.action,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
