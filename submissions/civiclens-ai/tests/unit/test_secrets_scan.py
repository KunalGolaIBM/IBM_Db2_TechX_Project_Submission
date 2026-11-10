import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_secrets_in_tracked_or_untracked_files():
    proc = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "src/backend/scripts/check_secrets.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout


def test_scanner_detects_planted_secrets(tmp_path):
    sys.path.insert(0, str(ROOT / "src/backend/scripts"))
    import check_secrets

    bad = tmp_path / "x.py"
    fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"  # built at runtime so this file stays clean
    fake_pw = "Sup3r" + "RealPassw0rd"
    bad.write_text(f'OPENAI_API_KEY = "{fake_key}"\nDB2_PASSWORD = "{fake_pw}"\n')
    env = tmp_path / ".env"
    env.write_text("A=b\n")
    monkey_root = check_secrets.ROOT
    check_secrets.ROOT = tmp_path
    try:
        findings = check_secrets.scan([bad, env], [])
    finally:
        check_secrets.ROOT = monkey_root
    text = "\n".join(findings)
    assert "credential shape" in text and "suspicious secret assignment" in text and "forbidden file" in text
