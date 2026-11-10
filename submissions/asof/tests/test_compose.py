"""docker-compose.yml, as every supported Compose reads it (README path C)."""
from __future__ import annotations

import pathlib
import re


def test_compose_has_no_required_variable_inside_a_fallback():
    """Compose 2.40 evaluates ${A:-${B:?message}} even when A is set, so this pattern fails there (path C)."""
    compose = (pathlib.Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text()
    assert not re.search(r"\$\{[^}]*:-\$\{[^}]*:\?", compose)
    assert "${DB2_PASSWORD:-${DB2_ADMIN_PASSWORD:-}}" in compose
