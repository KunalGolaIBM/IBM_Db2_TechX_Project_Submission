"""Create (idempotently) the CivicLens schema in IBM Db2.

Usage:  python scripts/db2_migrate.py
"""

import json

import _bootstrap  # noqa: F401
from civiclens.config import get_settings
from civiclens.db.connection import session
from civiclens.db.migrate import migrate


def main() -> None:
    settings = get_settings()
    print(f"Target: {settings.redacted_target()} schema={settings.db2_schema}")
    with session(settings) as db:
        print(json.dumps(migrate(db), indent=2))


if __name__ == "__main__":
    main()
