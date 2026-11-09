"""FastAPI dependencies."""

from __future__ import annotations

import logging
from collections.abc import Iterator

from fastapi import HTTPException

from civiclens.db.connection import Db2Session, Db2UnavailableError, connect

logger = logging.getLogger("civiclens")


def get_db() -> Iterator[Db2Session]:
    """One Db2 connection per request.

    Endpoints must declare their authentication dependency *before* this one so unauthenticated
    callers never cause a database connection. The 503 body is deliberately generic: the reason
    (which may name the host and user) is logged server-side only.
    """
    try:
        db = connect()
    except (Db2UnavailableError, RuntimeError) as exc:
        logger.warning("Database unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "DB_UNAVAILABLE", "message": "The database is temporarily unavailable."},
        ) from None
    try:
        yield db
    finally:
        db.close()
