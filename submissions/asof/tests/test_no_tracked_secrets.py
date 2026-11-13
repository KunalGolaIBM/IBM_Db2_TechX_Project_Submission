"""Nothing secret is ever tracked by git: no key, keystore, .env or anchor state, and no local secret value.

The submission is disqualified for a committed secret, and the organizers' validator rejects .env, .pem,
.key and similar files, so this fails the build first. It runs on what git tracks, so it skips outside a
git checkout (a source archive has no index to check)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

from asof.config import PROJECT_ROOT, Settings
from asof.setup import SetupError, ensure_anchor_key


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "--", "."], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return [line for line in out.stdout.splitlines() if line]


def _scanner():
    spec = importlib.util.spec_from_file_location("check_secrets", PROJECT_ROOT / "scripts" / "check_secrets.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SECRET_NAMES = (".key", ".pem", ".p12", ".pfx", ".kdb", ".sth", ".jks", ".crt", ".arm")


def test_no_key_keystore_env_or_anchor_file_is_tracked():
    bad = [p for p in _tracked()
           if p.lower().endswith(SECRET_NAMES) or p.startswith("var/") or "anchors-" in Path(p).name
           or (Path(p).name.startswith(".env") and Path(p).name != ".env.example")
           or Path(p).name in ("id_rsa", "id_ed25519", "anchor.key")]
    assert bad == []


def test_no_local_secret_value_appears_in_any_tracked_file():
    """The real values from .env (passwords, tokens, keys) and the anchor key file, wherever they are."""
    scanner = _scanner()
    real_env = os.environ.pop("ASOF_ANCHOR_KEY_FILE", None)  # look at the real key file, not the test stand-in
    try:
        values = scanner.local_secret_values()
    finally:
        if real_env is not None:
            os.environ["ASOF_ANCHOR_KEY_FILE"] = real_env
    leaks = [path for path in _tracked() if (PROJECT_ROOT / path).is_file()
             for line in (PROJECT_ROOT / path).read_text(encoding="utf-8", errors="ignore").splitlines()
             if any(scanner.leaks(v, line) for v in values)]
    assert leaks == []


def test_gitignore_keeps_runtime_secrets_and_state_out():
    probes = ["var/anchors/anchors-ASOF.jsonl", "var/tls/db2-server.arm", ".env", ".env.local"]
    out = subprocess.run(["git", "check-ignore", "--no-index", *probes], cwd=PROJECT_ROOT, capture_output=True, text=True)
    if out.returncode == 128:
        pytest.skip("not a git checkout")
    assert sorted(out.stdout.split()) == sorted(probes)


def test_the_default_anchor_key_file_is_outside_the_project_folder():
    s = Settings(_env_file=None, asof_anchor_key_file=None)
    assert not s.anchor_key_path.resolve().is_relative_to(PROJECT_ROOT.resolve())


def test_setup_creates_the_key_file_private_and_moves_an_old_env_key_out(tmp_path, monkeypatch):
    monkeypatch.delenv("ASOF_ANCHOR_KEY", raising=False)
    env = tmp_path / "env"
    env.write_text("DB2_PASSWORD=x\nASOF_ANCHOR_KEY=" + "k" * 43 + "\n")
    key_file = tmp_path / "cfg" / "asof" / "anchor.key"
    s = Settings(_env_file=env, asof_anchor_key_file=str(key_file))
    assert "moved from .env" in ensure_anchor_key(s, env)
    assert key_file.read_text().strip() == "k" * 43 and oct(key_file.stat().st_mode & 0o777) == "0o600"
    assert oct(key_file.parent.stat().st_mode & 0o777) == "0o700"
    assert "ASOF_ANCHOR_KEY=\n" in env.read_text() and "k" * 43 not in env.read_text()
    assert Settings(_env_file=env, asof_anchor_key_file=str(key_file)).anchor_key == b"k" * 43
    fresh = tmp_path / "fresh.key"
    assert "generated" in ensure_anchor_key(Settings(_env_file=None, asof_anchor_key_file=str(fresh)), env)
    assert len(fresh.read_text().strip()) == 43


def test_a_key_file_inside_the_project_or_readable_by_others_is_refused(tmp_path):
    from asof.config import ConfigError

    with pytest.raises(SetupError, match="inside the project folder"):
        ensure_anchor_key(Settings(_env_file=None, asof_anchor_key_file=str(PROJECT_ROOT / "var" / "anchor.key")))
    loose = tmp_path / "loose.key"
    loose.write_text("k" * 43)
    loose.chmod(0o644)
    with pytest.raises(ConfigError, match="chmod 600"):
        _ = Settings(_env_file=None, asof_anchor_key_file=str(loose)).anchor_key
