"""Repository hygiene: no credentials in source, tests or fixtures."""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Matches assignments of a non-trivial literal to a credential-looking name.
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:password|passwd|secret|api[_-]?key|token)\b
    \s*[:=]\s*
    ["']          # opening quote
    [^"'\s]{6,}   # a real-looking value (placeholders like "" pass)
    ["']
    """
)


def _python_files() -> list[Path]:
    return [
        p
        for p in BACKEND_ROOT.rglob("*.py")
        if "__pycache__" not in p.parts and ".venv" not in p.parts
    ]


def test_no_hardcoded_credentials_in_source():
    offenders: list[str] = []
    for path in _python_files():
        for match in _CREDENTIAL_ASSIGNMENT.finditer(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match.group(0)!r}")
    assert offenders == [], f"credential-like literals found: {offenders}"


def test_env_example_has_no_real_secrets():
    env_example = BACKEND_ROOT.parent / ".env.example"
    assert env_example.exists()
    for line in env_example.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if any(t in key.upper() for t in ("PASSWORD", "SECRET", "TOKEN", "KEY")):
            assert value == "", f"{key} must be a placeholder, found a value"


def test_dotenv_file_is_never_tracked_by_git():
    import subprocess

    repo_root = BACKEND_ROOT.parent
    # A local .env may exist for real-mode experiments (it is gitignored);
    # what must never happen is git tracking it.
    tracked = subprocess.run(
        ["git", "ls-files", ".env"],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert tracked.stdout.strip() == "", ".env must never be tracked by git"


def test_gitignore_covers_sensitive_paths():
    gitignore = (BACKEND_ROOT.parent / ".gitignore").read_text(encoding="utf-8")
    for required in (".env", ".venv/", "__pycache__/", "*.pem", "node_modules/"):
        assert required in gitignore, f".gitignore missing {required}"
