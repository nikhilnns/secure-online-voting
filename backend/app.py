"""Application factory for the Secure Online Voting Management System."""
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from backend.config import BASE_DIR, Config
from backend.controllers.auth_controller import ensure_admin
from backend.extensions import db
from backend.middleware.security import apply_security_headers
from backend.routes.admin_routes import admin_bp
from backend.routes.auth_routes import auth_bp
from backend.routes.election_routes import election_bp
from backend.routes.vote_routes import vote_bp
from backend.utils.errors import ServiceError


def register_error_handlers(app: Flask) -> None:
    """Return JSON errors for API requests."""

    @app.errorhandler(ServiceError)
    def handle_service_error(err):
        return jsonify({"error": err.message}), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": err.description}), err.code
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err):  # pragma: no cover - safety net
        app.logger.exception("Unhandled error: %s", err)
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


def create_app(config_class=Config) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(__name__,
                template_folder=str(BASE_DIR / "frontend" / "templates"),
                static_folder=str(BASE_DIR / "frontend" / "static"))
    app.config.from_object(config_class)

    db.init_app(app)
    for blueprint in (auth_bp, election_bp, vote_bp, admin_bp):
        app.register_blueprint(blueprint)
    register_error_handlers(app)
    app.after_request(apply_security_headers)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"}), 200

    with app.app_context():
        db.create_all()
        ensure_admin(app.config["ADMIN_EMAIL"], app.config["ADMIN_PASSWORD"])

    return app
