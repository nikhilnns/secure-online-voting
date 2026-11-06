"""Security middleware: response headers, CORS policy and rate limiting."""
import time
from collections import defaultdict, deque
from functools import wraps
from threading import Lock

from flask import current_app, jsonify, request

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def apply_security_headers(response):
    """Attach hardening headers to every response."""
    response.headers["Content-Security-Policy"] = CSP
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        origin = request.headers.get("Origin")
        if origin and origin in current_app.config.get("ALLOWED_ORIGINS", []):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE"
    return response


class RateLimiter:
    """Simple in-memory sliding-window limiter keyed by client IP."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        """Record a hit and return False when the limit is exceeded."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def reset(self):
        """Clear all counters (used by tests)."""
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def rate_limited(config_key: str):
    """Decorator limiting a view to ``app.config[config_key]`` requests/minute/IP."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            key = f"{view.__name__}:{request.remote_addr}"
            if not limiter.allow(key, current_app.config[config_key]):
                return jsonify({"error": "Too many requests, try again later"}), 429
            return view(*args, **kwargs)
        return wrapper
    return decorator
