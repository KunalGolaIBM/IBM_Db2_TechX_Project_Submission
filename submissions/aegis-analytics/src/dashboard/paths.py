"""Resolve project-root paths regardless of Streamlit working directory."""

from __future__ import annotations

from pathlib import Path

# dashboard/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_project_cwd() -> Path:
    """Streamlit may start with CWD elsewhere; anchor to project root."""
    import os

    os.chdir(PROJECT_ROOT)
    return PROJECT_ROOT
