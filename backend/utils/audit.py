"""Audit-trail helper."""
from flask import has_request_context, request

from backend.extensions import db
from backend.models import AuditLog


def log_action(action: str, actor_id=None, details: str = "") -> None:
    """Add an audit entry to the current session (committed by the caller)."""
    ip_address = (request.remote_addr or "") if has_request_context() else ""
    db.session.add(AuditLog(actor_id=actor_id, action=action,
                            details=details[:500], ip_address=ip_address))
