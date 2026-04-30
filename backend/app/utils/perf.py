"""
Performance instrumentation helpers.
"""
import os
import time
import logging

from flask import g, request
from sqlalchemy import event

logger = logging.getLogger(__name__)


def register_request_timing(app):
    slow_request_ms = float(os.getenv("REQUEST_SLOW_MS", "500"))

    @app.before_request
    def _mark_request_start():
        g._request_start = time.perf_counter()

    @app.after_request
    def _log_request_time(response):
        start = getattr(g, "_request_start", None)
        if start is None:
            return response

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"

        if elapsed_ms >= slow_request_ms:
            logger.warning(
                "Slow request %.1fms %s %s status=%s",
                elapsed_ms,
                request.method,
                request.path,
                response.status_code,
            )
        return response


def register_query_timing(app, db):
    if app.extensions.get("tradewise_query_timing_registered"):
        return

    slow_query_ms = float(os.getenv("SQL_SLOW_QUERY_MS", "200"))

    @event.listens_for(db.engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(db.engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        starts = conn.info.get("query_start_time") or []
        if not starts:
            return

        elapsed_ms = (time.perf_counter() - starts.pop()) * 1000
        if elapsed_ms >= slow_query_ms:
            compact_sql = " ".join(str(statement).split())
            logger.warning("Slow SQL %.1fms: %s", elapsed_ms, compact_sql[:500])

    app.extensions["tradewise_query_timing_registered"] = True
