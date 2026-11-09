"""Pytest configuration for PACT submission tests."""

import os
import sys
from pathlib import Path

# Add src to sys.path so tests can import api, core, db directly
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Optionally load environment variables from .env if present
env_file = BASE_DIR / ".env"
if not env_file.is_file():
    # Also check workspace root .env if running from workspace
    env_file = BASE_DIR.parent.parent.parent / ".env"

if env_file.is_file():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k not in os.environ:
                    os.environ[k] = v

