"""Save one game twice and query Db2-backed history/analytics.

Run after the API and Db2 schema are ready:
    python -m backend.scripts.demo_api
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from ..app.config import load_environment


load_environment()
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")


def request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> None:
    game_id = str(uuid4())
    payload = {
        "client_game_id": game_id,
        "pgn": (
            '[Event "TechX API Demo"]\n[Result "1-0"]\n\n'
            "1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"
        ),
        "result": "1-0",
        "termination": "checkmate",
        "player_color": "white",
        "source": "played",
        "opponent_elo": 1200,
        "time_control": "5 min",
        "played_at": datetime.now(timezone.utc).isoformat(),
        "opening_eco": "C20",
        "opening_name": "King's Pawn Game",
        "analysis": [],
    }
    first_status, first = request("POST", "/games", payload)
    retry_status, retry = request("POST", "/games", payload)
    list_status, games = request("GET", "/games?limit=5&offset=0")
    summary_status, summary = request("GET", "/analytics/summary")

    assert first_status == 201 and first.get("created") is True, (first_status, first)
    assert retry_status == 200 and retry.get("created") is False, (retry_status, retry)
    assert list_status == 200 and any(item["game_id"] == game_id for item in games["items"])
    assert summary_status == 200 and summary["total_games"] >= 1
    print(json.dumps({"saved_game_id": game_id, "idempotent_retry": True, "analytics": summary}, indent=2))


if __name__ == "__main__":
    main()

