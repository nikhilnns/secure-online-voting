"""Application configuration.

Values are read from environment variables so that secrets never live in the
source code. Sensible development defaults are provided.
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def _load_or_create_secret(filename: str) -> str:
    """Return a persistent random secret stored in the instance folder.

    Keeps JWT tokens and ledger hashes valid across restarts without
    hard-coding a secret in the repository.
    """
    INSTANCE_DIR.mkdir(exist_ok=True)
    path = INSTANCE_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = secrets.token_hex(32)
    path.write_text(value, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover - e.g. Windows file systems
        pass
    return value


class Config:  # pylint: disable=too-few-public-methods
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY") or _load_or_create_secret(".secret_key")
    LEDGER_KEY = os.environ.get("LEDGER_KEY") or _load_or_create_secret(".ledger_key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{INSTANCE_DIR / 'voting.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_EXPIRES_MIN", "60")))
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15
    LOGIN_RATE_LIMIT = int(os.environ.get("LOGIN_RATE_LIMIT", "10"))  # per minute per IP
    ALLOWED_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@vote.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@1234")
    MAX_CONTENT_LENGTH = 64 * 1024  # 64 KB request bodies are plenty for this API
    TESTING = False


class TestConfig(Config):  # pylint: disable=too-few-public-methods
    """Configuration used by the automated test-suite."""

    TESTING = True
    # Fresh random secrets per test run - nothing sensitive is hard-coded.
    SECRET_KEY = secrets.token_hex(32)
    LEDGER_KEY = secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    LOGIN_RATE_LIMIT = 1000
    ADMIN_PASSWORD = "T" + secrets.token_urlsafe(16) + "a1"
