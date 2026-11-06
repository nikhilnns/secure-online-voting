"""Business logic for registration and login."""
from datetime import datetime, timedelta, timezone

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from backend.extensions import db
from backend.middleware.auth import create_token
from backend.middleware.validation import (validate_email, validate_name,
                                           validate_password, validate_voter_id)
from backend.models import User
from backend.utils.audit import log_action
from backend.utils.errors import ServiceError

# Pre-computed hash used to keep login timing constant for unknown e-mails.
_DUMMY_HASH = generate_password_hash("timing-equaliser-not-a-real-password")


def _as_utc(value):
    """SQLite drops tzinfo; treat naive datetimes as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def register_voter(data: dict) -> User:
    """Create a new voter account in the *pending* state."""
    errors = {
        "full_name": validate_name(data.get("full_name")),
        "email": validate_email(data.get("email")),
        "voter_id": validate_voter_id(data.get("voter_id")),
        "password": validate_password(data.get("password")),
    }
    errors = {k: v for k, v in errors.items() if v}
    if errors:
        raise ServiceError("; ".join(errors.values()))

    email = data["email"].strip().lower()
    voter_id = data["voter_id"].strip().upper()
    if User.query.filter((User.email == email) | (User.voter_id == voter_id)).first():
        raise ServiceError("An account with this email or voter ID already exists", 409)

    user = User(full_name=data["full_name"].strip(), email=email, voter_id=voter_id,
                password_hash=generate_password_hash(data["password"]),
                role="voter", status="pending")
    db.session.add(user)
    db.session.flush()
    log_action("REGISTER", user.id, f"Voter {voter_id} registered")
    db.session.commit()
    return user


def login(data: dict) -> dict:
    """Authenticate a user and return a JWT plus profile.

    Implements account lockout after repeated failures and a generic error
    message so attackers cannot enumerate registered e-mails.
    """
    email = data.get("email")
    password = data.get("password")
    if validate_email(email) or not isinstance(password, str) or not password:
        raise ServiceError("Email and password are required")

    user = User.query.filter_by(email=email.strip().lower()).first()
    now = datetime.now(timezone.utc)

    if user is None:
        check_password_hash(_DUMMY_HASH, password)
        raise ServiceError("Invalid email or password", 401)

    locked_until = _as_utc(user.locked_until)
    if locked_until and locked_until > now:
        raise ServiceError("Account temporarily locked due to failed logins", 423)

    if not check_password_hash(user.password_hash, password):
        user.failed_logins += 1
        if user.failed_logins >= current_app.config["MAX_FAILED_LOGINS"]:
            user.locked_until = now + timedelta(minutes=current_app.config["LOCKOUT_MINUTES"])
            user.failed_logins = 0
            log_action("ACCOUNT_LOCKED", user.id, "Too many failed logins")
        else:
            log_action("LOGIN_FAILED", user.id, "Wrong password")
        db.session.commit()
        raise ServiceError("Invalid email or password", 401)

    if user.status == "rejected":
        raise ServiceError("Your registration was rejected by the administrator", 403)

    user.failed_logins = 0
    user.locked_until = None
    log_action("LOGIN", user.id, "Successful login")
    db.session.commit()
    return {"token": create_token(user), "user": user.to_dict()}


def ensure_admin(email: str, password: str) -> User:
    """Create the bootstrap administrator if it does not exist yet."""
    admin = User.query.filter_by(email=email.lower()).first()
    if admin is None:
        admin = User(full_name="System Administrator", email=email.lower(), voter_id="ADMIN0001",
                     password_hash=generate_password_hash(password), role="admin",
                     status="approved")
        db.session.add(admin)
        db.session.commit()
    return admin
