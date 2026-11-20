"""Guard against syntax errors in entry points that the other tests do not import."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_every_source_file_parses(path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
