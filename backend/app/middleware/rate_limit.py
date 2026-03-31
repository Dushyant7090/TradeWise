"""
Rate Limit Middleware - Request rate limiting per client/endpoint.

Uses a simple in-memory sliding-window counter. For production deployments,
replace with a Redis-backed solution (e.g., flask-limiter with Redis storage).
"""
from functools import wraps
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from flask import jsonify, request


# In-memory store: {key: [(timestamp, count), ...]}
_request_log: dict = defaultdict(list)

_DEFAULT_LIMIT = 60   # requests
_DEFAULT_WINDOW = 60  # seconds


def rate_limit(limit: int = _DEFAULT_LIMIT, window: int = _DEFAULT_WINDOW):
    """Decorator: limit requests to *limit* per *window* seconds per IP + endpoint."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            endpoint = request.endpoint or "unknown"
            key = f"{ip}:{endpoint}"
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=window)

            # Prune old entries
            _request_log[key] = [ts for ts in _request_log[key] if ts > cutoff]

            if len(_request_log[key]) >= limit:
                return jsonify({
                    "error": "Too Many Requests",
                    "message": f"Rate limit of {limit} requests per {window}s exceeded.",
                }), 429

            _request_log[key].append(now)
            return f(*args, **kwargs)
        return decorated
    return decorator
