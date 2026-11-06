"""Authentication API routes."""
from flask import Blueprint, g, jsonify

from backend.controllers import auth_controller
from backend.middleware.auth import token_required
from backend.middleware.security import rate_limited
from backend.middleware.validation import get_json_body

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
@rate_limited("LOGIN_RATE_LIMIT")
def register():
    """Register a new voter (pending admin approval)."""
    user = auth_controller.register_voter(get_json_body())
    return jsonify({"message": "Registration successful. Await administrator approval.",
                    "user": user.to_dict()}), 201


@auth_bp.post("/login")
@rate_limited("LOGIN_RATE_LIMIT")
def login():
    """Exchange credentials for a JWT."""
    return jsonify(auth_controller.login(get_json_body())), 200


@auth_bp.get("/me")
@token_required
def me():
    """Return the current user's profile."""
    return jsonify({"user": g.current_user.to_dict()}), 200
