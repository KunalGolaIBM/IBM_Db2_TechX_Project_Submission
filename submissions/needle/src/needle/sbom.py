"""Synthetic service fleet + SBOM deploy history, and the exposure statement (owner: app agent).

The fleet is SYNTHETIC: services, teams and deploy dates are fictional and generated
deterministically (fixed seed). Package names and versions are REAL PyPI releases chosen from
upgrade paths whose versions real OSV advisories list in affected[].versions; ``--check``
proves that against data/docs.jsonl.

Exposure semantics (contract addendum):
- AFFECTED            the version deployed now (FOR BUSINESS_TIME AS OF CURRENT DATE) is listed by the
                      advisory for the same PEP 503 package name: an exact package+version match.
- PREVIOUSLY_AFFECTED an earlier, now-ended run of listed versions.
- NOT_CONFIRMED       the service deploys the package but the deployed version is not listed.
                      This is never "safe": the advisory may use ranges, or the data may be incomplete.
- UNKNOWN_COVERAGE    the advisory names a deployed package (ADV_DOC.PACKAGES) but enumerates no versions for it
                      (OSV ranges only): not checked.
Semantic similarity never marks a service affected; only the SQL join does.

Run from the needle/ folder with PYTHONPATH=src:
    python -m needle.sbom --check          # verify the chosen versions against data/docs.jsonl
    python -m needle.sbom --csv            # write data/sbom_fleet.csv
    python -m needle.sbom --load           # run sql/05_sbom_temporal.sql and (re)insert the fleet (db2inst1)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SQL_FILE = ROOT / "sql" / "05_sbom_temporal.sql"

SEED = 2026
SEED_TODAY = date(2026, 11, 1)  # last possible upgrade date in the generated history
OPEN_END = date(9999, 12, 31)   # BUS_END of the version deployed now

_PEP503 = re.compile(r"[-_.]+")


def normalize_pkg(name: str) -> str:
    """PEP 503 normalized project name: lowercase, runs of '-', '_', '.' -> '-'."""
    return _PEP503.sub("-", name.strip()).lower()


# Real PyPI release sequences (oldest -> newest). Exposure is decided by ADV_AFFECTED, not here.
UPGRADE_PATHS: dict[str, list[str]] = {
    "pyyaml": ["5.1", "5.3", "5.3.1", "5.4.1", "6.0.1"],
    "jinja2": ["2.10", "2.11.2", "3.1.2", "3.1.4", "3.1.6"],
    "urllib3": ["1.25.8", "1.26.5", "1.26.18", "2.2.2", "2.5.0"],
    "requests": ["2.19.1", "2.25.1", "2.28.2", "2.31.0", "2.32.3", "2.32.5"],
    "pillow": ["8.1.0", "9.0.0", "10.0.1", "10.3.0", "11.3.0"],
    "django": ["2.2.10", "3.2.25", "4.2.11", "4.2.20", "5.1.8"],
    "flask": ["0.12.2", "1.0", "2.2.4", "2.3.2", "3.1.1"],
    "werkzeug": ["0.15.3", "2.2.2", "2.3.7", "3.0.3", "3.0.6"],
    "cryptography": ["3.3.2", "38.0.0", "41.0.7", "42.0.4", "44.0.1"],
    "aiohttp": ["3.8.1", "3.9.1", "3.9.4", "3.10.11", "3.12.14"],
    "gunicorn": ["19.9.0", "20.1.0", "21.2.0", "22.0.0", "23.0.0"],
    "fastapi": ["0.65.1", "0.95.0", "0.109.0", "0.109.1", "0.115.0"],
    "starlette": ["0.27.0", "0.36.3", "0.40.0", "0.47.2"],
    "python-multipart": ["0.0.6", "0.0.7", "0.0.18", "0.0.20"],
    "sqlparse": ["0.4.1", "0.4.4", "0.5.0"],
    "tornado": ["6.1", "6.3.2", "6.4.1", "6.5"],
    "mlflow": ["1.30.0", "2.9.2", "2.12.1", "2.17.0"],
    "transformers": ["4.30.0", "4.36.0", "4.48.0", "4.53.0"],
    "pyarrow": ["13.0.0", "14.0.0", "14.0.1", "17.0.0"],
    "scikit-learn": ["0.24.1", "1.4.1.post1", "1.5.0"],
    "numpy": ["1.16.0", "1.21.0", "1.22.0", "1.26.4"],
    "paramiko": ["2.7.2", "3.3.1", "3.4.0"],
    "pyjwt": ["1.7.1", "2.4.0", "2.10.1"],
    "protobuf": ["3.20.1", "4.21.5", "4.25.3", "4.25.8"],
    "lxml": ["4.6.2", "4.6.5", "4.9.1", "5.3.0"],
    "celery": ["4.4.7", "5.2.2", "5.3.6"],
    "redis": ["4.3.5", "4.5.3", "4.5.4", "5.0.1"],
    "sqlalchemy": ["1.3.0", "1.4.46", "2.0.25"],
    "joblib": ["1.1.0", "1.2.0", "1.4.2"],
    "markdown": ["3.3.4", "3.8", "3.8.1"],
    "bleach": ["3.1.0", "3.3.0", "6.1.0"],
    "pydantic": ["1.6.1", "1.10.2", "1.10.13", "2.11.7"],
    "httpx": ["0.22.0", "0.23.0", "0.27.0"],
    "certifi": ["2022.9.24", "2022.12.7", "2023.7.22", "2024.7.4"],
    "idna": ["2.10", "3.6", "3.7", "3.10"],
    "setuptools": ["58.1.0", "65.5.1", "70.0.0", "78.1.1"],
}


# First PyPI upload date of each version (pypi.org/pypi/<pkg>/json, fetched 2026-11-09). A synthetic deploy of a
# version never starts before its real release.
RELEASE_DATES: dict[str, dict[str, str]] = {
    "pyyaml": {"5.1": "2019-03-13", "5.3": "2020-01-06", "5.3.1": "2020-03-18", "5.4.1": "2021-01-20", "6.0.1": "2023-07-17"},
    "jinja2": {"2.10": "2017-11-08", "2.11.2": "2020-04-13", "3.1.2": "2022-04-28", "3.1.4": "2024-05-05", "3.1.6": "2025-03-05"},
    "urllib3": {"1.25.8": "2020-01-21", "1.26.5": "2021-05-26", "1.26.18": "2023-10-17", "2.2.2": "2024-06-17", "2.5.0": "2025-06-18"},
    "requests": {"2.19.1": "2018-06-14", "2.25.1": "2020-12-16", "2.28.2": "2023-01-12", "2.31.0": "2023-05-22", "2.32.3": "2024-05-29", "2.32.5": "2025-08-18"},
    "pillow": {"8.1.0": "2021-01-02", "9.0.0": "2022-01-02", "10.0.1": "2023-09-15", "10.3.0": "2024-04-01", "11.3.0": "2025-07-01"},
    "django": {"2.2.10": "2020-02-03", "3.2.25": "2024-03-04", "4.2.11": "2024-03-04", "4.2.20": "2025-03-06", "5.1.8": "2025-04-02"},
    "flask": {"0.12.2": "2017-05-16", "1.0": "2018-04-26", "2.2.4": "2023-04-25", "2.3.2": "2023-05-01", "3.1.1": "2025-05-13"},
    "werkzeug": {"0.15.3": "2019-05-14", "2.2.2": "2022-08-08", "2.3.7": "2023-08-14", "3.0.3": "2024-05-05", "3.0.6": "2024-10-25"},
    "cryptography": {"3.3.2": "2021-02-07", "38.0.0": "2022-09-07", "41.0.7": "2023-11-28", "42.0.4": "2024-02-21", "44.0.1": "2025-02-11"},
    "aiohttp": {"3.8.1": "2021-11-14", "3.9.1": "2023-11-26", "3.9.4": "2024-04-11", "3.10.11": "2024-11-13", "3.12.14": "2025-07-10"},
    "gunicorn": {"19.9.0": "2018-07-03", "20.1.0": "2021-03-27", "21.2.0": "2023-07-19", "22.0.0": "2024-04-16", "23.0.0": "2024-08-10"},
    "fastapi": {"0.65.1": "2021-05-11", "0.95.0": "2023-03-18", "0.109.0": "2024-01-11", "0.109.1": "2024-02-03", "0.115.0": "2024-09-17"},
    "starlette": {"0.27.0": "2023-05-16", "0.36.3": "2024-02-04", "0.40.0": "2024-10-15", "0.47.2": "2025-07-20"},
    "python-multipart": {"0.0.6": "2023-02-27", "0.0.7": "2024-02-03", "0.0.18": "2024-11-28", "0.0.20": "2024-12-16"},
    "sqlparse": {"0.4.1": "2020-10-08", "0.4.4": "2023-04-18", "0.5.0": "2024-04-13"},
    "tornado": {"6.1": "2020-10-30", "6.3.2": "2023-05-14", "6.4.1": "2024-06-06", "6.5": "2025-05-15"},
    "mlflow": {"1.30.0": "2022-10-20", "2.9.2": "2023-12-14", "2.12.1": "2024-04-17", "2.17.0": "2024-10-12"},
    "transformers": {"4.30.0": "2023-06-08", "4.36.0": "2023-12-11", "4.48.0": "2025-01-10", "4.53.0": "2025-06-26"},
    "pyarrow": {"13.0.0": "2023-08-23", "14.0.0": "2023-11-01", "14.0.1": "2023-11-08", "17.0.0": "2024-07-16"},
    "scikit-learn": {"0.24.1": "2021-01-19", "1.4.1.post1": "2024-02-16", "1.5.0": "2024-05-21"},
    "numpy": {"1.16.0": "2019-01-14", "1.21.0": "2021-06-22", "1.22.0": "2021-12-31", "1.26.4": "2024-02-05"},
    "paramiko": {"2.7.2": "2020-08-30", "3.3.1": "2023-07-28", "3.4.0": "2023-12-18"},
    "pyjwt": {"1.7.1": "2018-12-07", "2.4.0": "2022-05-12", "2.10.1": "2024-11-28"},
    "protobuf": {"3.20.1": "2022-04-22", "4.21.5": "2022-08-09", "4.25.3": "2024-02-15", "4.25.8": "2025-05-28"},
    "lxml": {"4.6.2": "2020-11-27", "4.6.5": "2021-12-12", "4.9.1": "2022-07-01", "5.3.0": "2024-08-10"},
    "celery": {"4.4.7": "2020-07-31", "5.2.2": "2021-12-26", "5.3.6": "2023-11-22"},
    "redis": {"4.3.5": "2022-11-22", "4.5.3": "2023-03-22", "4.5.4": "2023-03-29", "5.0.1": "2023-09-26"},
    "sqlalchemy": {"1.3.0": "2019-03-04", "1.4.46": "2023-01-03", "2.0.25": "2024-01-03"},
    "joblib": {"1.1.0": "2021-10-07", "1.2.0": "2022-09-16", "1.4.2": "2024-05-02"},
    "markdown": {"3.3.4": "2021-02-24", "3.8": "2025-04-11", "3.8.1": "2025-06-18"},
    "bleach": {"3.1.0": "2019-01-09", "3.3.0": "2021-02-01", "6.1.0": "2023-10-06"},
    "pydantic": {"1.6.1": "2020-07-15", "1.10.2": "2022-09-05", "1.10.13": "2023-09-27", "2.11.7": "2025-06-14"},
    "httpx": {"0.22.0": "2022-01-26", "0.23.0": "2022-05-23", "0.27.0": "2024-02-21"},
    "certifi": {"2022.9.24": "2022-09-24", "2022.12.7": "2022-12-07", "2023.7.22": "2023-07-22", "2024.7.4": "2024-07-04"},
    "idna": {"2.10": "2020-06-27", "3.6": "2023-11-25", "3.7": "2024-04-11", "3.10": "2024-09-15"},
    "setuptools": {"58.1.0": "2021-09-22", "65.5.1": "2022-11-04", "70.0.0": "2024-05-21", "78.1.1": "2025-04-19"},
}


def released(pkg: str, version: str) -> date:
    return date.fromisoformat(RELEASE_DATES[pkg][version])


@dataclass(frozen=True)
class Service:
    service_id: str
    name: str
    owner_team: str
    born: date
    packages: tuple[str, ...]
    stale_after: date | None = None  # the team stopped upgrading after this date


# Fictional services (SYNTHETIC). Names are generic on purpose.
SERVICES: tuple[Service, ...] = (
    Service("SVC-01", "payments-api", "payments", date(2020, 3, 2),
            ("django", "requests", "urllib3", "cryptography", "pyjwt", "celery", "redis", "gunicorn")),
    Service("SVC-02", "checkout-web", "web-platform", date(2020, 9, 14),
            ("flask", "werkzeug", "jinja2", "requests", "gunicorn")),
    Service("SVC-03", "ml-feature-store", "ml-platform", date(2021, 4, 6),
            ("pyarrow", "numpy", "scikit-learn", "sqlalchemy", "pyyaml", "fastapi", "starlette")),
    Service("SVC-04", "model-serving-gateway", "ml-platform", date(2022, 1, 10),
            ("fastapi", "starlette", "python-multipart", "transformers", "pydantic", "httpx")),
    Service("SVC-05", "experiment-tracker", "ml-platform", date(2021, 8, 23),
            ("mlflow", "sqlalchemy", "flask", "pyyaml", "protobuf")),
    Service("SVC-06", "image-thumbnailer", "media", date(2020, 6, 1),
            ("pillow", "aiohttp", "numpy")),
    Service("SVC-07", "docs-renderer", "devex", date(2020, 11, 30),
            ("markdown", "bleach", "jinja2", "pyyaml", "lxml"), stale_after=date(2023, 3, 1)),
    Service("SVC-08", "notifications-worker", "comms", date(2021, 2, 15),
            ("celery", "redis", "requests", "jinja2")),
    Service("SVC-09", "auth-service", "identity", date(2020, 2, 3),
            ("django", "pyjwt", "cryptography", "idna", "certifi")),
    Service("SVC-10", "ledger-reconciler", "finance-eng", date(2020, 7, 20),
            ("sqlalchemy", "sqlparse", "pyyaml", "paramiko")),
    Service("SVC-11", "search-indexer", "search", date(2021, 6, 7),
            ("aiohttp", "lxml", "urllib3", "protobuf")),
    Service("SVC-12", "admin-portal", "internal-tools", date(2020, 10, 12),
            ("django", "pillow", "sqlparse", "gunicorn"), stale_after=date(2024, 2, 1)),
    Service("SVC-13", "ci-artifact-scanner", "devex", date(2021, 1, 18),
            ("pyyaml", "requests", "setuptools", "cryptography")),
    Service("SVC-14", "data-export-api", "data-eng", date(2022, 5, 2),
            ("fastapi", "starlette", "pydantic", "pyarrow", "python-multipart")),
    Service("SVC-15", "chat-assistant-backend", "ml-platform", date(2023, 2, 6),
            ("transformers", "httpx", "tornado", "pydantic")),
    Service("SVC-16", "legacy-reporting", "finance-eng", date(2020, 1, 13),
            ("flask", "jinja2", "werkzeug", "pyyaml"), stale_after=date(2021, 5, 1)),
    Service("SVC-17", "sftp-ingest", "data-eng", date(2020, 4, 27),
            ("paramiko", "cryptography", "setuptools"), stale_after=date(2022, 9, 1)),
    Service("SVC-18", "webhook-relay", "platform", date(2021, 9, 13),
            ("aiohttp", "tornado", "certifi", "idna")),
    Service("SVC-19", "geo-tiles", "media", date(2022, 3, 21),
            ("pillow", "numpy", "protobuf")),
    Service("SVC-20", "status-page", "sre", date(2021, 11, 1),
            ("flask", "jinja2", "markdown", "requests")),
)


@dataclass(frozen=True)
class Component:
    service_id: str
    package: str
    version: str
    bus_start: date
    bus_end: date


def generate_fleet(seed: int = SEED, today: date = SEED_TODAY) -> list[Component]:
    """Deterministic deploy history: adjacent periods [start, end), the last one open-ended.

    A service starts on the newest release available at its birth minus 0-2 versions (teams pin old
    versions), then upgrades every 150-520 days, never to a version before its real release date
    (+7-60 days), and never after ``stale_after`` (teams that stopped upgrading) or ``today``.
    """
    out: list[Component] = []
    for svc in SERVICES:
        for pkg in svc.packages:
            path = UPGRADE_PATHS[pkg]
            rng = random.Random(f"{seed}:{svc.service_id}:{pkg}")  # str seed: stable across runs
            born = svc.born + timedelta(days=rng.randint(0, 45))
            avail = [i for i, v in enumerate(path) if released(pkg, v) <= born]
            idx = max(0, (avail[-1] if avail else 0) - rng.choice((0, 1, 1, 2)))
            start = max(born, released(pkg, path[idx]) + timedelta(days=rng.randint(7, 60)))
            stop = min(today, svc.stale_after) if svc.stale_after else today
            while True:
                nidx = min(len(path) - 1, idx + rng.choice((1, 1, 1, 2)))
                nxt = max(start + timedelta(days=rng.randint(150, 520)),
                          released(pkg, path[nidx]) + timedelta(days=rng.randint(7, 60)))
                if idx >= len(path) - 1 or nxt > stop:
                    out.append(Component(svc.service_id, normalize_pkg(pkg), path[idx], start, OPEN_END))
                    break
                out.append(Component(svc.service_id, normalize_pkg(pkg), path[idx], start, nxt))
                idx, start = nidx, nxt
    return out


# ----------------------------------------------------------------------------------------------
# Exposure: one SQL statement (Db2 does the work) + a pure-Python mirror used by the unit tests.
# ----------------------------------------------------------------------------------------------

EXPOSURE_SQL_TEMPLATE = """\
WITH AFF (ADV_ID, PACKAGE, VERSION) AS (
  SELECT DISTINCT A.ADV_ID, LOWER(REGEXP_REPLACE(A.PACKAGE, '[-_.]+', '-')), A.VERSION
  FROM NEEDLE.ADV_AFFECTED A
  WHERE A.ECOSYSTEM = 'PyPI'
    AND A.ADV_ID IN ({marks})
    AND EXISTS (SELECT 1 FROM NEEDLE.ADV_DOC D WHERE D.ADV_ID = A.ADV_ID)   -- RCAC applies here
),
HIT AS (            -- every deploy period (full history) whose exact version the advisory lists
  SELECT S.SERVICE_ID, S.PACKAGE, S.VERSION, S.BUS_START, S.BUS_END, F.ADV_ID
  FROM NEEDLE.SBOM_COMPONENT S
  JOIN AFF F ON F.PACKAGE = S.PACKAGE AND F.VERSION = S.VERSION
),
EDGE AS (           -- a new run starts when the previous listed period does not end where this one starts
  SELECT H.SERVICE_ID, H.PACKAGE, H.VERSION, H.BUS_START, H.BUS_END, H.ADV_ID,
         CASE WHEN LAG(H.BUS_END) OVER (PARTITION BY H.SERVICE_ID, H.PACKAGE, H.ADV_ID
                                        ORDER BY H.BUS_START) = H.BUS_START THEN 0 ELSE 1 END AS NEW_RUN
  FROM HIT H
),
RUNS AS (
  SELECT E.SERVICE_ID, E.PACKAGE, E.VERSION, E.BUS_START, E.BUS_END, E.ADV_ID,
         SUM(E.NEW_RUN) OVER (PARTITION BY E.SERVICE_ID, E.PACKAGE, E.ADV_ID ORDER BY E.BUS_START
                              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS RUN_NO
  FROM EDGE E
),
WIN AS (            -- contiguous exposure windows
  SELECT R.SERVICE_ID, R.PACKAGE, R.ADV_ID, R.RUN_NO,
         MIN(R.BUS_START) AS EXPOSED_SINCE, MAX(R.BUS_END) AS RUN_END,
         LISTAGG(R.VERSION, ' > ') WITHIN GROUP (ORDER BY R.BUS_START) AS VERSIONS
  FROM RUNS R
  GROUP BY R.SERVICE_ID, R.PACKAGE, R.ADV_ID, R.RUN_NO
),
NOW_ALL AS (        -- what is deployed today
  SELECT C.SERVICE_ID, C.PACKAGE, C.VERSION
  FROM NEEDLE.SBOM_COMPONENT FOR BUSINESS_TIME AS OF CURRENT DATE C
),
NOW_HIT AS (        -- affected now: exact package + version match on today's deployment
  SELECT N.SERVICE_ID, N.PACKAGE, N.VERSION, F.ADV_ID
  FROM NOW_ALL N
  JOIN AFF F ON F.PACKAGE = N.PACKAGE AND F.VERSION = N.VERSION
),
ADV_PKG AS (        -- package names each visible advisory mentions (ADV_DOC.PACKAGES, PEP 503, ', ' list)
  SELECT D.ADV_ID, ', ' || LOWER(REGEXP_REPLACE(COALESCE(D.PACKAGES, ''), '[-_.]+', '-')) || ',' AS PKGS
  FROM NEEDLE.ADV_DOC D
  WHERE D.ADV_ID IN ({marks})                                                -- RCAC applies here
)
SELECT W.SERVICE_ID, V.NAME AS SERVICE, V.OWNER_TEAM, V.SYNTHETIC, W.PACKAGE,
       N.VERSION AS VERSION_NOW, W.ADV_ID,
       CASE WHEN N.ADV_ID IS NOT NULL THEN 'AFFECTED' ELSE 'PREVIOUSLY_AFFECTED' END AS STATUS,
       W.EXPOSED_SINCE,
       CASE WHEN N.ADV_ID IS NOT NULL THEN CAST(NULL AS DATE) ELSE W.RUN_END END AS EXPOSED_UNTIL,
       DAYS(LEAST(W.RUN_END, CURRENT DATE)) - DAYS(W.EXPOSED_SINCE) AS DAYS_EXPOSED,
       CAST(W.VERSIONS AS VARCHAR(4000)) AS VERSIONS
FROM WIN W
JOIN NEEDLE.SERVICE V ON V.SERVICE_ID = W.SERVICE_ID
LEFT JOIN NOW_HIT N ON N.SERVICE_ID = W.SERVICE_ID AND N.PACKAGE = W.PACKAGE AND N.ADV_ID = W.ADV_ID
                   AND W.EXPOSED_SINCE <= CURRENT DATE AND W.RUN_END > CURRENT DATE
UNION ALL
SELECT N.SERVICE_ID, V.NAME, V.OWNER_TEAM, V.SYNTHETIC, N.PACKAGE, N.VERSION, P.ADV_ID,
       'NOT_CONFIRMED', CAST(NULL AS DATE), CAST(NULL AS DATE), CAST(NULL AS INTEGER),
       CAST(NULL AS VARCHAR(4000))
FROM NOW_ALL N
JOIN (SELECT DISTINCT ADV_ID, PACKAGE FROM AFF) P ON P.PACKAGE = N.PACKAGE
JOIN NEEDLE.SERVICE V ON V.SERVICE_ID = N.SERVICE_ID
WHERE NOT EXISTS (SELECT 1 FROM NOW_HIT X
                  WHERE X.SERVICE_ID = N.SERVICE_ID AND X.PACKAGE = N.PACKAGE AND X.ADV_ID = P.ADV_ID)
UNION ALL           -- the advisory names a deployed package but enumerates no versions for it (ranges only)
SELECT N.SERVICE_ID, V.NAME, V.OWNER_TEAM, V.SYNTHETIC, N.PACKAGE, N.VERSION, P.ADV_ID,
       'UNKNOWN_COVERAGE', CAST(NULL AS DATE), CAST(NULL AS DATE), CAST(NULL AS INTEGER),
       CAST(NULL AS VARCHAR(4000))
FROM NOW_ALL N
JOIN ADV_PKG P ON LOCATE(', ' || N.PACKAGE || ',', P.PKGS) > 0
JOIN NEEDLE.SERVICE V ON V.SERVICE_ID = N.SERVICE_ID
WHERE NOT EXISTS (SELECT 1 FROM AFF X WHERE X.ADV_ID = P.ADV_ID AND X.PACKAGE = N.PACKAGE)
ORDER BY STATUS, SERVICE, PACKAGE, ADV_ID"""

# Status meanings (UI and LLM prompt use the same words):
STATUS_HELP = {
    "AFFECTED": "deployed version is listed by the advisory (exact package + version match)",
    "PREVIOUSLY_AFFECTED": "an earlier, now-ended run of listed versions",
    "NOT_CONFIRMED": "package deployed, deployed version not listed; never 'safe'",
    "UNKNOWN_COVERAGE": "version ranges not enumerated in OSV; not checked",
}

EXPOSURE_COLUMNS = ("SERVICE_ID", "SERVICE", "OWNER_TEAM", "SYNTHETIC", "PACKAGE", "VERSION_NOW", "ADV_ID",
                    "STATUS", "EXPOSED_SINCE", "EXPOSED_UNTIL", "DAYS_EXPOSED", "VERSIONS")


def exposure_sql(n_ids: int) -> str:
    """The exposure statement; the id list appears twice, so it has 2 * ``n_ids`` markers (no interpolated values)."""
    n = int(n_ids)
    if n < 1:
        raise ValueError("need at least one advisory id")
    return EXPOSURE_SQL_TEMPLATE.format(marks=", ".join("?" * n))


def fetch_exposure(conn: Any, adv_ids: Sequence[str]) -> list[dict]:
    """Run the exposure statement on the CALLER'S connection (RCAC applies). Empty ids -> []."""
    import ibm_db

    ids = list(dict.fromkeys(a for a in adv_ids if a))
    if not ids:
        return []
    stmt = ibm_db.prepare(conn, exposure_sql(len(ids)))
    ibm_db.execute(stmt, tuple(ids) * 2)
    rows: list[dict] = []
    r = ibm_db.fetch_assoc(stmt)
    while r:
        rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
        r = ibm_db.fetch_assoc(stmt)
    ibm_db.free_stmt(stmt)
    return rows


def compute_exposure(history: Iterable[dict], affected: Iterable[tuple[str, str, str]],
                     today: date, adv_packages: dict[str, Iterable[str]] | None = None) -> list[dict]:
    """Pure-Python mirror of EXPOSURE_SQL (no service join). Used for unit tests and cross-checks.

    history:      dicts with service_id, package, version, bus_start, bus_end (dates, end exclusive)
    affected:     (adv_id, package, version) tuples
    adv_packages: adv_id -> package names the advisory mentions (ADV_DOC.PACKAGES); a mentioned, deployed
                  package without any enumerated version gives UNKNOWN_COVERAGE
    """
    aff = {(a, normalize_pkg(p), v) for a, p, v in affected}
    adv_pkgs = {(a, p) for a, p, _ in aff}
    hist = [dict(h, package=normalize_pkg(h["package"])) for h in history]

    hits: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for h in hist:
        for a, p in adv_pkgs:
            if p == h["package"] and (a, p, h["version"]) in aff:
                hits[(h["service_id"], p, a)].append(h)

    now = {(h["service_id"], h["package"]): h["version"] for h in hist
           if h["bus_start"] <= today < h["bus_end"]}

    out: list[dict] = []
    for (svc, pkg, adv), periods in hits.items():
        periods.sort(key=lambda h: h["bus_start"])
        runs: list[list[dict]] = []
        for h in periods:
            if runs and runs[-1][-1]["bus_end"] == h["bus_start"]:
                runs[-1].append(h)
            else:
                runs.append([h])
        for run in runs:
            since, end = run[0]["bus_start"], run[-1]["bus_end"]
            v_now = now.get((svc, pkg))
            current = since <= today < end and v_now is not None and (adv, pkg, v_now) in aff
            out.append({
                "SERVICE_ID": svc, "PACKAGE": pkg, "ADV_ID": adv,
                "VERSION_NOW": v_now if current else None,
                "STATUS": "AFFECTED" if current else "PREVIOUSLY_AFFECTED",
                "EXPOSED_SINCE": since,
                "EXPOSED_UNTIL": None if current else end,
                "DAYS_EXPOSED": (min(end, today) - since).days,
                "VERSIONS": " > ".join(h["version"] for h in run),
            })
    for (svc, pkg), v_now in now.items():
        for a, p in adv_pkgs:
            if p == pkg and (a, p, v_now) not in aff:
                out.append({"SERVICE_ID": svc, "PACKAGE": pkg, "ADV_ID": a, "VERSION_NOW": v_now,
                            "STATUS": "NOT_CONFIRMED", "EXPOSED_SINCE": None, "EXPOSED_UNTIL": None,
                            "DAYS_EXPOSED": None, "VERSIONS": None})
        for a, names in (adv_packages or {}).items():
            if pkg in {normalize_pkg(n) for n in names} and (a, pkg) not in adv_pkgs:
                out.append({"SERVICE_ID": svc, "PACKAGE": pkg, "ADV_ID": a, "VERSION_NOW": v_now,
                            "STATUS": "UNKNOWN_COVERAGE", "EXPOSED_SINCE": None, "EXPOSED_UNTIL": None,
                            "DAYS_EXPOSED": None, "VERSIONS": None})
    out.sort(key=lambda r: (r["STATUS"], r["SERVICE_ID"], r["PACKAGE"], r["ADV_ID"]))
    return out


# ----------------------------------------------------------------------------------------------
# DB helpers (the orchestrator's db.py may replace these; integration point).
# ----------------------------------------------------------------------------------------------

def _env() -> dict[str, str]:
    from dotenv import dotenv_values

    vals = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    vals.update({k: v for k, v in os.environ.items() if k.startswith(("DB2_", "NDL_", "OLLAMA", "LLM_", "EMBED_"))})
    return vals


def password_for(authid: str, env: dict[str, str] | None = None) -> str | None:
    """Look up a user's password in needle/.env. Accepted keys: <AUTHID>_PASSWORD, DB2_PASSWORD_<AUTHID>,
    and DB2_PASSWORD when authid is DB2_USER."""
    env = env if env is not None else _env()
    a = authid.upper()
    for key in (f"{a}_PASSWORD", f"DB2_PASSWORD_{a}", f"{a}_PWD"):
        if env.get(key):
            return env[key]
    if a == (env.get("DB2_USER") or "").upper():
        return env.get("DB2_PASSWORD")
    return None


_AUTHID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,29}$")
_BAD_PWD_CHARS = re.compile(r"[;{}\r\n\x00]")


def connect_as(authid: str | None = None, timeout_s: int = 10, password: str | None = None) -> Any:
    """Open an ibm_db connection as ``authid`` (default DB2_USER). Caller closes it in ``finally``.

    ``password`` given: use exactly these credentials (the app's login form). Otherwise look the user up in
    needle/.env (scripts, tests, and the opt-in demo identity switcher). ibm_db ignores separate user/password
    arguments when the DSN is a keyword string (SQL30082N reason 17), so UID/PWD go into the string and are
    validated first: no ';', '{', '}' or line breaks can inject connection keywords.
    """
    import ibm_db

    env = _env()
    user = (authid or env.get("DB2_USER", "db2inst1")).strip()
    if not _AUTHID_RE.match(user):
        raise ValueError("Db2 user ID must be 1-30 letters, digits or '_' and start with a letter")
    pwd = password if password is not None else password_for(user, env)
    if not pwd:
        raise RuntimeError(f"no password for {user}")
    if _BAD_PWD_CHARS.search(pwd):
        raise ValueError("password contains ';', '{', '}' or a line break, which this client cannot pass safely")
    cs = (f"DATABASE={env.get('DB2_DATABASE', 'VECDB')};HOSTNAME={env.get('DB2_HOST', 'localhost')};"
          f"PORT={env.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;UID={user};PWD={pwd};"
          f"ConnectTimeout={int(timeout_s)};")
    return ibm_db.connect(cs, "", "")


def _split_sql(text: str) -> tuple[list[str], list[str]]:
    """Split the SQL file into (pre-load, post-load) statements on ';' (no procedures in this file)."""
    pre, _, post = text.partition("-- @POST_LOAD")

    def stmts(chunk: str) -> list[str]:
        body = "\n".join(l for l in chunk.splitlines() if not l.strip().startswith("--"))
        return [s.strip() for s in body.split(";") if s.strip()]

    return stmts(pre), stmts(post)


def load(conn: Any, components: list[Component]) -> dict[str, int]:
    """Create the tables if missing, replace the fleet, run RUNSTATS. Returns row counts."""
    import ibm_db

    pre, post = _split_sql(SQL_FILE.read_text(encoding="utf-8"))
    for s in pre:
        try:
            ibm_db.exec_immediate(conn, s)
        except Exception as e:  # re-runnable: object already exists / grant already held
            if "SQL0601N" not in str(e) and "SQL0554N" not in str(e) and "SQL0605W" not in str(e):
                raise
    ibm_db.exec_immediate(conn, "DELETE FROM NEEDLE.SBOM_COMPONENT")
    ibm_db.exec_immediate(conn, "DELETE FROM NEEDLE.SERVICE")
    st = ibm_db.prepare(conn, "INSERT INTO NEEDLE.SERVICE (SERVICE_ID, NAME, OWNER_TEAM, SYNTHETIC) "
                              "VALUES (?, ?, ?, 1)")
    ibm_db.execute_many(st, tuple((s.service_id, s.name, s.owner_team) for s in SERVICES))
    st = ibm_db.prepare(conn, "INSERT INTO NEEDLE.SBOM_COMPONENT (SERVICE_ID, PACKAGE, VERSION, BUS_START, BUS_END) "
                              "VALUES (?, ?, ?, ?, ?)")
    ibm_db.execute_many(st, tuple((c.service_id, c.package, c.version, c.bus_start.isoformat(),
                                   c.bus_end.isoformat()) for c in components))
    for s in post:
        ibm_db.exec_immediate(conn, s)
    counts = {}
    for t in ("SERVICE", "SBOM_COMPONENT"):
        r = ibm_db.fetch_tuple(ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM NEEDLE.{t}"))
        counts[t] = int(r[0])
    return counts


def check_against_docs(components: list[Component], docs_path: Path = DATA / "docs.jsonl") -> dict:
    """Count, per (package, version) in the fleet, the non-withdrawn advisories listing it in docs.jsonl."""
    want = {(c.package, c.version) for c in components}
    pkgs = {p for p, _ in want}
    hits: dict[tuple[str, str], set[str]] = defaultdict(set)
    with open(docs_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("withdrawn"):
                continue
            for eco, pkg, ver in d.get("affected") or []:
                if eco != "PyPI":
                    continue
                p = normalize_pkg(pkg)
                if p in pkgs and (p, ver) in want:
                    hits[(p, ver)].add(d["adv_id"])
    listed = {k: len(v) for k, v in hits.items()}
    return {"pairs": len(want), "listed_pairs": len(listed),
            "per_pair": {f"{p}=={v}": listed.get((p, v), 0) for p, v in sorted(want)}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify versions against data/docs.jsonl")
    ap.add_argument("--csv", action="store_true", help="write data/sbom_fleet.csv")
    ap.add_argument("--load", action="store_true", help="create tables + (re)insert the fleet as DB2_USER")
    args = ap.parse_args(argv)

    comps = generate_fleet()
    now = [c for c in comps if c.bus_end == OPEN_END]
    print(f"services={len(SERVICES)} components={len(comps)} deployed_now={len(now)} seed={SEED}")
    if args.check:
        rep = check_against_docs(comps)
        print(f"(package, version) pairs={rep['pairs']} listed_by_>=1_advisory={rep['listed_pairs']}")
        for k, v in rep["per_pair"].items():
            print(f"  {k:32s} advisories={v}")
    if args.csv:
        DATA.mkdir(exist_ok=True)
        out = DATA / "sbom_fleet.csv"
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SERVICE_ID", "NAME", "OWNER_TEAM", "PACKAGE", "VERSION", "BUS_START", "BUS_END"])
            names = {s.service_id: s for s in SERVICES}
            for c in comps:
                s = names[c.service_id]
                w.writerow([c.service_id, s.name, s.owner_team, c.package, c.version, c.bus_start, c.bus_end])
        print(f"wrote {out}")
    if args.load:
        import ibm_db

        conn = connect_as(None, timeout_s=20)
        try:
            print(load(conn, comps))
        finally:
            ibm_db.close(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
