"""DSN / connection helpers for the real Db2 adapters.

Security notes:
- The DSN NEVER contains credentials; uid/pwd are passed separately so DSN
  strings can appear in logs without leaking secrets.
- Error messages are sanitized (password value stripped) before surfacing.
"""

from __future__ import annotations

from app.core.config import Settings


def build_dsn(settings: Settings) -> str:
    """Build an ibm_db DSN (no credentials inside)."""
    return (
        f"DATABASE={settings.db2_dbname};"
        f"HOSTNAME={settings.db2_host};"
        f"PORT={settings.db2_port};"
        f"PROTOCOL=TCPIP;"
    )


def connect_args(settings: Settings) -> tuple[str, str, str]:
    """Return ``(dsn, user, password)`` for ``ibm_db_dbi.connect``."""
    return (
        build_dsn(settings),
        settings.db2_ro_user,
        settings.db2_ro_password.get_secret_value(),
    )


def admin_connect_args(settings: Settings) -> tuple[str, str, str]:
    """``(dsn, user, password)`` for the privileged *maintenance* account.

    Used ONLY by approved-action execution. Distinct from the read-only
    account so the query path can never gain write privileges.
    """
    return (
        build_dsn(settings),
        settings.db2_admin_user,
        settings.db2_admin_password.get_secret_value(),
    )


def sqlalchemy_url(settings: Settings):
    """SQLAlchemy URL for the ``ibm_db_sa`` dialect (``db2+ibm_db://``).

    Lazily imports SQLAlchemy (an *integration* dependency, see
    requirements-integration.txt) so the mock-mode install never needs it.
    The password lives inside the returned ``URL`` object, whose ``repr``/
    ``str`` masks it — never format it into a plain string yourself.

    Usage::

        from sqlalchemy import create_engine
        engine = create_engine(sqlalchemy_url(settings))

    The shipped adapters use ``ibm_db_dbi`` directly (short-lived connections,
    SQLSTATE-level error mapping); this helper is for tooling/notebooks and
    LangChain/SQLAlchemy-based integrations that expect an ``Engine``.
    """
    from sqlalchemy.engine import URL

    return URL.create(
        "db2+ibm_db",
        username=settings.db2_ro_user,
        password=settings.db2_ro_password.get_secret_value() or None,
        host=settings.db2_host,
        port=settings.db2_port,
        database=settings.db2_dbname,
    )


def sanitize(message: str, settings: Settings) -> str:
    """Strip any credential material from an error message."""
    cleaned = message
    for secret in (
        settings.db2_ro_password.get_secret_value(),
        settings.db2_admin_password.get_secret_value(),
    ):
        if secret:
            cleaned = cleaned.replace(secret, "***")
    return cleaned[:300]
