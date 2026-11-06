"""The lock file must pin every package exactly and agree with requirements.txt."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?==([^\s;#]+)$")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _pins(path: Path) -> dict[str, str]:
    pins = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = PIN.match(line)
        assert m, f"{path.name}: not an exact pin: {line!r}"
        pins[_norm(m.group(1))] = m.group(3)
    return pins


def test_every_requirement_is_pinned_and_locked_at_the_same_version():
    direct = _pins(ROOT / "requirements.txt")
    locked = _pins(ROOT / "requirements.lock")
    assert direct, "requirements.txt is empty"
    mismatched = {name: (v, locked.get(name)) for name, v in direct.items() if locked.get(name) != v}
    assert not mismatched, f"requirements.txt and requirements.lock disagree: {mismatched}"


def test_lock_covers_transitive_dependencies_and_has_no_local_paths():
    text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    locked = _pins(ROOT / "requirements.lock")
    assert len(locked) > 2 * len(_pins(ROOT / "requirements.txt")), "lock looks like it only has direct pins"
    assert "file://" not in text and " @ " not in text and "-e " not in text


def test_dev_tools_are_pinned():
    dev = _pins(ROOT / "requirements-dev.txt")
    assert {"pip-audit", "ruff"} <= set(dev)
