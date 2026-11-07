#!/usr/bin/env python3
"""Non-LLM security and adversarial checks against the live API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.errors import ConfigurationError, LLMUnavailableError  # noqa: E402
from app.services.llm import LangChainLLMClient  # noqa: E402

API = "http://127.0.0.1:8000"
OUT = ROOT / "reports" / "security_results.json"


def upload(client: httpx.Client, filename: str, content: bytes, title: str | None = None):
    data = {"title": title} if title else {}
    return client.post(
        f"{API}/api/documents",
        files={"file": (filename, content, "text/plain")},
        data=data,
        timeout=60,
    )


def main() -> int:
    results = {}
    client = httpx.Client()

    cases = []
    response = upload(client, "malformed.pdf", b"%PDF-1.4 this is not a real PDF", "bad pdf")
    cases.append({"case": "malformed_pdf", "status": response.status_code, "passed": response.status_code == 422})
    response = upload(client, "payload.exe", b"MZ")
    cases.append({"case": "unsupported_extension", "status": response.status_code, "passed": response.status_code == 400})
    response = upload(client, "empty.txt", b"")
    cases.append({"case": "empty_upload", "status": response.status_code, "passed": response.status_code == 400})
    response = upload(client, "big.txt", b"x" * (10 * 1024 * 1024 + 1))
    cases.append({"case": "oversized_upload", "status": response.status_code, "passed": response.status_code in (400, 413)})

    # Invalid UTF-8: current loader falls back to latin-1.
    response = upload(client, "invalid.txt", b"\xff\xfe legitimate evidence \x80", "invalid utf8")
    cases.append(
        {
            "case": "invalid_utf8",
            "status": response.status_code,
            "passed": response.status_code in (201, 400, 422),
            "note": "Decodes with latin-1; documented behavior, not a crash.",
        }
    )

    # SQL injection payload in metadata and passage text.
    marker = "security-check"
    injection = "Robert'); DROP TABLE AEGIS.DOCUMENTS; --"
    response = upload(client, "injection.txt", f"{injection} {marker} evidence text.".encode(), injection)
    sql_passed = response.status_code == 201
    if sql_passed:
        document_id = response.json()["document_id"]
        detail = client.get(f"{API}/api/documents/{document_id}")
        sql_passed = detail.status_code == 200 and injection in detail.text
    # Ensure the table still exists and is queryable.
    health = client.get(f"{API}/api/db/health")
    sql_passed = sql_passed and health.status_code == 200 and "DOCUMENTS" in health.text
    cases.append({"case": "sql_injection_metadata", "status": response.status_code, "passed": bool(sql_passed)})
    if sql_passed and response.status_code == 201:
        # No delete endpoint; leave the harmless test document or clean it through API? Document cleanup is via DB.
        pass

    # XSS payload is stored as data and returned as JSON; React escapes it at render.
    xss = "<script>alert('aegis')</script>"
    response = upload(client, "xss.txt", f"{xss} evidence".encode(), xss)
    xss_passed = response.status_code == 201 and xss in response.text
    cases.append({"case": "xss_stored_as_data", "status": response.status_code, "passed": bool(xss_passed)})

    # Path traversal in filename is sanitized.
    response = upload(client, "../../evil.txt", b"path traversal evidence text", "traversal")
    sanitized = response.status_code == 201 and response.json().get("filename") == "evil.txt"
    cases.append({"case": "path_traversal_filename", "status": response.status_code, "passed": bool(sanitized)})

    # CORS preflight is explicit.
    preflight = client.options(
        f"{API}/api/verify",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    cases.append(
        {
            "case": "cors_preflight",
            "status": preflight.status_code,
            "passed": preflight.status_code == 200
            and preflight.headers.get("access-control-allow-origin") == "http://localhost:3000",
        }
    )

    results["http_cases"] = cases

    # Missing LLM key.
    settings = get_settings()
    try:
        LangChainLLMClient(settings.model_copy(update={"llm_api_key": ""}))
        missing_key_passed = False
    except ConfigurationError:
        missing_key_passed = True
    results["missing_llm_key"] = {"passed": missing_key_passed}

    # Unreachable LLM endpoint: safe 503 class, no secret echo.
    try:
        bad = LangChainLLMClient(
            settings.model_copy(
                update={
                    "llm_api_key": "not-a-real-key",
                    "llm_base_url": "http://127.0.0.1:9/v1",
                    "llm_timeout_seconds": 2,
                    "llm_max_retries": 0,
                }
            )
        )
        bad.complete("test", "test")
        unreachable_passed = False
        unreachable_message = ""
    except LLMUnavailableError as exc:
        unreachable_passed = "not-a-real-key" not in exc.message
        unreachable_message = exc.message
    results["unreachable_llm"] = {
        "passed": unreachable_passed,
        "message": unreachable_message,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
