"""
Lightweight in-process response cache for read-heavy API endpoints.
"""
import hashlib
import json
import threading
import time
from functools import wraps

from flask import make_response, request
from flask_jwt_extended import get_jwt_identity

_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _now() -> float:
    return time.time()


def _stable_query_string() -> str:
    items = sorted((request.args or {}).items())
    if not items:
        return ""
    return "&".join(f"{k}={v}" for k, v in items)


def _safe_identity() -> str:
    try:
        identity = get_jwt_identity()
    except Exception:
        identity = None
    return str(identity or "anon")


def _cache_key(key_prefix: str, vary_by_user: bool) -> str:
    pieces = [
        key_prefix,
        request.method,
        request.path,
        _stable_query_string(),
    ]
    if vary_by_user:
        pieces.append(_safe_identity())

    key_material = "|".join(pieces)
    digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    return f"{key_prefix}:{digest}"


def cache_response(ttl_seconds: int = 20, key_prefix: str = "resp", vary_by_user: bool = True):
    """Cache successful GET responses for a short TTL."""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if request.method != "GET":
                return fn(*args, **kwargs)

            key = _cache_key(key_prefix, vary_by_user)
            now_ts = _now()

            with _CACHE_LOCK:
                entry = _CACHE.get(key)
                if entry and entry["expires_at"] > now_ts:
                    response = make_response(entry["body"], entry["status_code"])
                    for header, value in entry["headers"].items():
                        response.headers[header] = value
                    response.headers["X-Cache"] = "HIT"
                    return response

            response = make_response(fn(*args, **kwargs))
            if response.status_code >= 400:
                return response

            cached_headers = {
                "Content-Type": response.headers.get("Content-Type", "application/json"),
            }
            with _CACHE_LOCK:
                _CACHE[key] = {
                    "body": response.get_data(),
                    "status_code": response.status_code,
                    "headers": cached_headers,
                    "expires_at": now_ts + max(1, int(ttl_seconds)),
                }
            response.headers["X-Cache"] = "MISS"
            return response

        return wrapper

    return decorator


def invalidate_cache(prefix: str = ""):
    """Invalidate cache entries containing a prefix string in their cache key."""
    with _CACHE_LOCK:
        if not prefix:
            _CACHE.clear()
            return

        to_delete = [key for key in _CACHE if prefix in key]
        for key in to_delete:
            del _CACHE[key]


def cache_stats() -> str:
    """Return a tiny JSON summary useful for diagnostics."""
    with _CACHE_LOCK:
        stats = {
            "entries": len(_CACHE),
            "keys": list(_CACHE.keys())[:25],
        }
    return json.dumps(stats)
