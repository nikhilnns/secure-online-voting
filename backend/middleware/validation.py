"""Input validation helpers.

Each validator returns an error message string, or ``None`` when the value is valid.
"""
import re

from flask import request

from backend.utils.errors import ServiceError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
VOTER_ID_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,119}$")


def validate_email(email) -> str | None:
    """Validate an e-mail address."""
    if not isinstance(email, str) or not email.strip():
        return "Email is required"
    if len(email) > 120 or not EMAIL_RE.match(email.strip()):
        return "Invalid email format"
    return None


def validate_password(password) -> str | None:
    """Enforce a minimum password policy."""
    if not isinstance(password, str) or not password:
        return "Password is required"
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 128:
        return "Password is too long"
    if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
        return "Password must contain upper and lower case letters"
    if not re.search(r"\d", password):
        return "Password must contain a digit"
    return None


def validate_voter_id(voter_id) -> str | None:
    """Voter / institutional ID: 4-20 alphanumeric characters."""
    if not isinstance(voter_id, str) or not VOTER_ID_RE.match(voter_id.strip()):
        return "Voter ID must be 4-20 alphanumeric characters"
    return None


def validate_name(name) -> str | None:
    """A human name."""
    if not isinstance(name, str) or not NAME_RE.match(name.strip()):
        return "Name must be 2-120 letters (spaces, . ' - allowed)"
    return None


def clean_text(value, max_len: int, field: str, required: bool = True) -> str:
    """Strip and length-check a free text field, raising ServiceError on failure."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ServiceError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise ServiceError(f"{field} is required")
    if len(value) > max_len:
        raise ServiceError(f"{field} must be at most {max_len} characters")
    return value


def get_json_body() -> dict:
    """Return the JSON request body as a dict or raise a 400 ServiceError."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ServiceError("Request body must be a JSON object")
    return data


def require_int(value, field: str) -> int:
    """Coerce a positive integer field."""
    if isinstance(value, bool):
        raise ServiceError(f"{field} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ServiceError(f"{field} must be a positive integer") from exc
    if number <= 0:
        raise ServiceError(f"{field} must be a positive integer")
    return number
