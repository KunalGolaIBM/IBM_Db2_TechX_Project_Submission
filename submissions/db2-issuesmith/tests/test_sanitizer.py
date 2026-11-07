from issuesmith.sanitizer import find_secrets, sanitize


def test_redacts_connection_string_parts():
    r = sanitize("DATABASE=testdb;HOSTNAME=db2.acme.corp;PORT=50000;UID=rahul;PWD=SuperSecret123;")
    assert "SuperSecret123" not in r.text and "rahul" not in r.text and "acme" not in r.text
    assert "DATABASE=testdb" in r.text and "PORT=50000" in r.text
    assert r.total >= 3


def test_redacts_tokens_urls_emails_and_user_paths():
    text = ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 https://bob:hunter2@proxy.x.local:3128 "
            "mail a.b@example.org /home/priya/.vscode C:\\Users\\Priya\\AppData Bearer abcdefghijklmnop1234")
    r = sanitize(text)
    for secret in ("ghp_", "hunter2", "a.b@example.org", "priya", "Priya", "abcdefghijklmnop1234"):
        assert secret not in r.text


def test_keeps_public_endpoints_versions_and_localhost():
    text = ("curl: (28) Failed to connect to download.docker.com port 443; archive.ubuntu.com; "
            "Db2 version 12.1.5.0; Linux 5.15.167.4-microsoft-standard-WSL2; HOSTNAME=localhost; 127.0.0.1")
    r = sanitize(text)
    assert r.text == text
    assert r.total == 0


def test_private_ip_redacted():
    assert "10.12.4.7" not in sanitize("connect ECONNREFUSED 10.12.4.7:50000").text


def test_sanitised_output_is_clean_on_rescan():
    r = sanitize("PWD=abc123; password: 'xyz789' user=bob HOSTNAME=db.internal")
    assert find_secrets(r.text) == []
