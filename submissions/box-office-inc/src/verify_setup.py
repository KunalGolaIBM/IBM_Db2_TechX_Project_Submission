from __future__ import annotations

import importlib
import json
import os
import sys
from typing import Any, Dict

from db2_client import build_connection_string, test_connection
from strategy_engine import build_strategy


def check_dependency(name: str) -> Dict[str, Any]:
    try:
        module = importlib.import_module(name)
        return {"name": name, "status": "ok", "version": getattr(module, "__version__", "unknown")}
    except Exception as exc:  # pragma: no cover
        return {"name": name, "status": "missing", "error": str(exc)}


def main() -> None:
    report: Dict[str, Any] = {
        "python_version": sys.version.split()[0],
        "db2_env_ready": bool(os.getenv("DB2_DSN") or (os.getenv("DB2_HOST") and os.getenv("DB2_DATABASE") and os.getenv("DB2_USER"))),
        "db2_connection_string": bool(build_connection_string()),
        "dependencies": {},
        "db2": test_connection(),
        "recommendation": build_strategy({
            "studio_name": "CineVerse Studio",
            "revenue": 2400000,
            "expenses": 1750000,
            "reputation": 82,
            "fanbase": 480000,
            "active_movies": 3,
            "marketing_budget": 350000,
            "market_trend": "rising",
        }),
    }

    for dependency in ["ibm_db", "dotenv", "langchain_core", "langchain_openai"]:
        report["dependencies"][dependency] = check_dependency(dependency)

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
