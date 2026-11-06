"""JWT authentication and role-based access control."""
from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from backend.extensions import db
from backend.models import User


def create_token(user: User) -> str:
    """Issue a signed, short-lived JWT for a user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + current_app.config["JWT_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"],
                      algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises jwt.PyJWTError on any problem."""
    return jwt.decode(token, current_app.config["SECRET_KEY"],
                      algorithms=[current_app.config["JWT_ALGORITHM"]],
                      options={"require": ["exp", "sub"]})


def _unauthorized(message: str, status: int = 401):
    return jsonify({"error": message}), status


def token_required(view):
    """Require a valid Bearer token; exposes the user as ``g.current_user``."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return _unauthorized("Authentication token missing")
        try:
            payload = decode_token(header[7:].strip())
        except jwt.ExpiredSignatureError:
            return _unauthorized("Token expired")
        except jwt.PyJWTError:
            return _unauthorized("Invalid token")
        user = db.session.get(User, int(payload["sub"]))
        if user is None:
            return _unauthorized("User no longer exists")
        g.current_user = user
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    """Require an authenticated administrator."""
    @wraps(view)
    @token_required
    def wrapper(*args, **kwargs):
        if g.current_user.role != "admin":
            return _unauthorized("Administrator access required", 403)
        return view(*args, **kwargs)
    return wrapper
