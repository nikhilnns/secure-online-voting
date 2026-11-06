"""Business logic for elections and candidates (administrator workflows)."""
from datetime import datetime, timezone

from backend.extensions import db
from backend.middleware.validation import clean_text
from backend.models import Ballot, Candidate, Election, VoteRecord
from backend.utils.audit import log_action
from backend.utils.errors import ServiceError

ALLOWED_TRANSITIONS = {"draft": "open", "open": "closed"}


def get_election(election_id: int) -> Election:
    """Fetch an election or raise 404."""
    election = db.session.get(Election, election_id)
    if election is None:
        raise ServiceError("Election not found", 404)
    return election


def list_elections(include_drafts: bool, user_id=None) -> list:
    """List elections; voters do not see drafts. Adds a has_voted flag for voters."""
    query = Election.query.order_by(Election.id.desc())
    if not include_drafts:
        query = query.filter(Election.status != "draft")
    voted = set()
    if user_id is not None:
        voted = {r.election_id for r in VoteRecord.query.filter_by(user_id=user_id).all()}
    result = []
    for election in query.all():
        item = election.to_dict()
        item["has_voted"] = election.id in voted
        result.append(item)
    return result


def create_election(data: dict, admin_id: int) -> Election:
    """Create a new election in draft state."""
    title = clean_text(data.get("title"), 150, "Title")
    description = clean_text(data.get("description"), 1000, "Description", required=False)
    election = Election(title=title, description=description, created_by=admin_id)
    db.session.add(election)
    db.session.flush()
    log_action("ELECTION_CREATED", admin_id, f"Election #{election.id} '{title}'")
    db.session.commit()
    return election


def add_candidate(election_id: int, data: dict, admin_id: int) -> Candidate:
    """Add a candidate; only allowed while the election is a draft."""
    election = get_election(election_id)
    if election.status != "draft":
        raise ServiceError("Candidates can only be added while the election is a draft", 409)
    name = clean_text(data.get("name"), 120, "Candidate name")
    affiliation = clean_text(data.get("affiliation"), 120, "Affiliation",
                             required=False) or "Independent"
    manifesto = clean_text(data.get("manifesto"), 500, "Manifesto", required=False)
    if any(c.name.lower() == name.lower() for c in election.candidates):
        raise ServiceError("A candidate with this name already exists in the election", 409)
    candidate = Candidate(election_id=election.id, name=name, affiliation=affiliation,
                          manifesto=manifesto)
    db.session.add(candidate)
    log_action("CANDIDATE_ADDED", admin_id, f"'{name}' added to election #{election.id}")
    db.session.commit()
    return candidate


def remove_candidate(election_id: int, candidate_id: int, admin_id: int) -> None:
    """Remove a candidate from a draft election."""
    election = get_election(election_id)
    if election.status != "draft":
        raise ServiceError("Candidates can only be removed while the election is a draft", 409)
    candidate = db.session.get(Candidate, candidate_id)
    if candidate is None or candidate.election_id != election.id:
        raise ServiceError("Candidate not found", 404)
    db.session.delete(candidate)
    log_action("CANDIDATE_REMOVED", admin_id, f"Candidate #{candidate_id} removed")
    db.session.commit()


def change_status(election_id: int, new_status: str, admin_id: int) -> Election:
    """Advance the election lifecycle: draft -> open -> closed (one way only)."""
    election = get_election(election_id)
    if ALLOWED_TRANSITIONS.get(election.status) != new_status:
        raise ServiceError(f"Cannot change status from '{election.status}' to '{new_status}'",
                           409)
    if new_status == "open" and len(election.candidates) < 2:
        raise ServiceError("An election needs at least two candidates before opening", 409)
    election.status = new_status
    now = datetime.now(timezone.utc)
    if new_status == "open":
        election.opened_at = now
    else:
        election.closed_at = now
    log_action(f"ELECTION_{new_status.upper()}", admin_id, f"Election #{election.id}")
    db.session.commit()
    return election


def delete_election(election_id: int, admin_id: int) -> None:
    """Delete a draft election (elections with ballots can never be deleted)."""
    election = get_election(election_id)
    if election.status != "draft" or Ballot.query.filter_by(election_id=election.id).count():
        raise ServiceError("Only draft elections without ballots can be deleted", 409)
    db.session.delete(election)
    log_action("ELECTION_DELETED", admin_id, f"Election #{election_id}")
    db.session.commit()
