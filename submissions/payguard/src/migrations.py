"""Versioned SQL migrations, serialized and checksummed in PG_META."""
from __future__ import annotations

import hashlib
import re
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "db" / "migrations"
log = logging.getLogger("payguard.migrations")


def migrate(repo, dim: int, directory: Path = ROOT) -> list[str]:
    if not 1 <= dim <= 32768:
        raise ValueError("Invalid embedding dimension")
    repo._try("CREATE TABLE PG_META (META_KEY VARCHAR(64) NOT NULL PRIMARY KEY, META_VALUE VARCHAR(512))",
              ignore=("42710",))
    level = repo.query("SELECT SERVICE_LEVEL FROM TABLE(SYSPROC.ENV_GET_INST_INFO()) AS I")[0]["service_level"]
    release = re.search(r"(?:v|^)(\d+)\.(\d+)\.(\d+)", level, flags=re.I)
    if not release:
        raise ValueError("Cannot identify Db2 service level")
    version = tuple(int(x) for x in release.groups())
    applied = []
    for path in sorted(directory.glob("[0-9][0-9][0-9]_*.sql")):
        content = path.read_text(encoding="utf-8")
        requirement = re.search(r"min-db2: ([\d.]+)", content)
        if requirement and version < tuple(int(x) for x in requirement[1].split(".")):
            continue  # deferred, not marked applied; upgrading the server will apply it
        checksum = hashlib.sha256(content.encode()).hexdigest()
        key = "migration:" + path.name
        optional_vector = "optional-capability: vector_indexes" in content
        try:
            with repo.transaction():
                repo.execute("LOCK TABLE PG_META IN EXCLUSIVE MODE")
                previous = repo.get_meta(key)
                if previous:
                    if previous != checksum:
                        raise ValueError(f"Applied migration changed: {path.name}")
                    continue
                sql = re.sub(r"--[^\n]*", "", content).replace("{{EMBED_DIM}}", str(dim))
                for statement in sql.split(";"):
                    if statement.strip():
                        repo._try(statement.strip(), ignore=("42710", "01550"))
                repo.set_meta(key, checksum)
                if optional_vector:
                    repo.set_meta("capability:vector_indexes", "enabled")
                applied.append(path.name)
        except Exception as exc:
            # Some 12.1.5 CE installations expose VECTOR but reject ANN index
            # creation (observed SQL0614/54008). Never mark that migration applied.
            unsupported = any(code in str(exc) for code in ("54008", 'error "-614"', "0A000", "42997"))
            if not optional_vector or not unsupported:
                raise
            repo.set_meta("capability:vector_indexes", "deferred: vector index unsupported; exact region-filtered search")
            log.warning("vector_indexes_deferred", extra={"error_type": type(exc).__name__})
    return applied
