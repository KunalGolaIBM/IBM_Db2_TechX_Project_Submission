from __future__ import annotations

import json
from typing import Any, Dict

from db2_client import persist_insight, test_connection
from strategy_engine import build_strategy


def sample_studio() -> Dict[str, Any]:
    return {
        "studio_name": "CineVerse Studio",
        "revenue": 2400000,
        "expenses": 1750000,
        "reputation": 82,
        "fanbase": 480000,
        "active_movies": 3,
        "marketing_budget": 350000,
        "market_trend": "rising",
    }


def main() -> None:
    studio = sample_studio()
    recommendation = build_strategy(studio)
    db2_status = test_connection()
    persistence = persist_insight(studio, recommendation)

    result = {
        "studio": studio,
        "db2_status": db2_status,
        "recommendation": recommendation,
        "persistence": persistence,
    }

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
