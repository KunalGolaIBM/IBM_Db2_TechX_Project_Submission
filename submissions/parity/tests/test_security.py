"""Security hygiene tests for the repo."""

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"


def test_bound_params_used_for_inserts():
    text = (SRC / "parity" / "sync" / "db2_admin.py").read_text(encoding="utf-8")
    assert "bind_param" in text
    assert "VALUES (?" in text or "VALUES ({marks})" in text


def test_no_hardcoded_api_key_in_src():
    hits = []
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if re.search(r"api_key\s*=\s*['\"][^'\"]+['\"]", text):
            hits.append(str(path))
    assert hits == []


def test_no_env_file_in_git_status():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore


def test_security_doc_exists():
    doc = (ROOT / "docs" / "security-review.md").read_text(encoding="utf-8")
    assert "bind_param" in doc or "bound parameters" in doc
    assert "No critical or high findings open" in doc
