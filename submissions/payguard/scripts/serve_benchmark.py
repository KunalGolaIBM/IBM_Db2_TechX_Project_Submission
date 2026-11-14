"""Run the real Db2 application with AI disabled and a high benchmark-only IP quota.

python scripts/serve_benchmark.py
The deployed app's default rate limit remains 60 per minute per IP.
"""
import os
import sys
from pathlib import Path

os.environ.update(GEMINI_API_KEY="", PAYPAL_CLIENT_ID="", PAYPAL_CLIENT_SECRET="",
                  EMBED_PROVIDER="local", RATE_LIMIT_PER_MINUTE="100000")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, access_log=False)
