"""Small server-side client for the FastAPI service used by Streamlit."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()


def call_api(method: str, path: str, role: str, payload: dict | None = None) -> dict:
    """Call the internal API using the configured demo role token."""
    role_tokens = {
        "VIEWER": os.getenv("VIEWER_TOKEN", "viewer_token"),
        "ANALYST": os.getenv("ANALYST_TOKEN", "analyst_token"),
        "DPO": os.getenv("DPO_TOKEN", "dpo_token"),
    }
    token = role_tokens.get(role)
    if not token:
        raise RuntimeError(f"No API token is configured for the {role} role.")

    base_url = os.getenv("API_BASE_URL", "http://localhost:8001").rstrip("/")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url}{path}",
        data=body,
        method=method.upper(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            content = response.read()
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("detail", str(error))
        except (ValueError, AttributeError):
            detail = str(error)
        raise RuntimeError(f"API returned {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the API at {base_url}: {error.reason}") from error

    return json.loads(content) if content else {}
