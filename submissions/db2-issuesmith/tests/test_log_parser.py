from conftest import SAMPLES
from issuesmith.log_parser import classify, extract_environment, extract_evidence, normalize_signature
from issuesmith.sanitizer import sanitize


def _load(name):
    return sanitize((SAMPLES / name).read_text()).text


def test_runtime_install_log():
    text = _load("01_wsl_runtime_install_failure.log")
    ev = extract_evidence(text)
    cat, conf = classify(ev)
    assert cat == "RUNTIME_INSTALL" and conf > 0.5
    labels = {e.label for e in ev}
    assert {"No container runtime", "All runtime installs failed", "Connection timed out"} <= labels
    env = extract_environment(text)
    assert env["linux_distribution"] == "Ubuntu 22.04.5 LTS"
    assert env["operating_system"] == "Windows with WSL"
    assert env["extension_version"] == "1.2.1"


def test_restart_log_keeps_success_observations():
    text = _load("02_quick_restart_stopped_container.log")
    ev = extract_evidence(text)
    assert classify(ev)[0] == "RESTART"
    kinds = {(e.label, e.kind) for e in ev}
    assert ("Exec on stopped container", "ERROR") in kinds
    assert ("Db2 accessible", "OBSERVATION") in kinds
    env = extract_environment(text)
    assert env["container_runtime"] == "Podman 3.4.4"
    assert env["db2_version"] == "12.1.5.0"
    assert env["container_image"] == "icr.io/db2_community/db2:latest"


def test_connection_log():
    ev = extract_evidence(_load("03_connection_refused.log"))
    assert classify(ev)[0] == "CONNECTION"


def test_signature_normalisation_is_stable():
    a = normalize_signature("2026-11-05 10:18:18.771 [error] curl: (28) Failed after 131072 ms")
    b = normalize_signature("2026-12-01 08:00:00.001 [error] curl: (28) Failed after 99 ms")
    assert a == b
