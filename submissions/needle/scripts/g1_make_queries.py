"""Embed 20 fixed triage-style queries on this PC (Ollama) -> data/g1_queries.json for the G1 EXPLAIN/timing run.

Run from needle/ with PYTHONPATH=src:  .venv\\Scripts\\python scripts\\g1_make_queries.py
"""
import json
from pathlib import Path

from needle.embed import embed_query

QUERIES = [
    "yaml loader allows arbitrary code execution when parsing untrusted input",
    "jinja template sandbox escape",
    "pickle deserialization remote code execution in machine learning library",
    "path traversal in file upload allows writing outside the target directory",
    "SSRF through an HTTP redirect in a URL fetcher",
    "regular expression denial of service in a markdown parser",
    "SQL injection in ORM raw query",
    "cross-site scripting in the admin interface",
    "malicious package exfiltrates environment variables on install",
    "typosquatting package steals credentials",
    "JWT signature verification bypass",
    "XML external entity injection",
    "tarfile extraction path traversal",
    "denial of service via crafted image file in imaging library",
    "open redirect in login next parameter",
    "CSRF token not validated",
    "prompt injection leads to code execution in an LLM agent framework",
    "heap buffer overflow in compression library",
    "certificate validation disabled allows man in the middle",
    "command injection via subprocess shell=True",
]

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "g1_queries.json"
    rows = [{"text": q, "vec": [round(x, 6) for x in embed_query(q)]} for q in QUERIES]
    out.write_text(json.dumps(rows), encoding="utf-8")
    print(f"wrote {out} n={len(rows)} dim={len(rows[0]['vec'])}")
