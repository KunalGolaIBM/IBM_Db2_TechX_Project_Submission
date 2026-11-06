"""The organizers' env names and the three Db2 setup paths (extension, IBM image, compose)."""

from __future__ import annotations

import subprocess

import pytest

from asof import setup
from asof.config import ConfigError, Settings


@pytest.fixture
def clean_env(monkeypatch):
    for key in ("DB2_USER", "DB2_PASSWORD", "DB2_ADMIN_USER", "DB2_ADMIN_PASSWORD", "DB2_CONTAINER"):
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_the_organizers_names_are_read(clean_env):
    clean_env.setenv("DB2_USER", "judge")
    clean_env.setenv("DB2_PASSWORD", "pw-new")
    s = Settings(_env_file=None)
    assert s.db2_admin_user == "judge" and s.db2_admin_password.get_secret_value() == "pw-new"


def test_the_older_names_still_work_and_the_new_ones_win(clean_env):
    clean_env.setenv("DB2_ADMIN_PASSWORD", "pw-old")
    assert Settings(_env_file=None).db2_admin_password.get_secret_value() == "pw-old"
    clean_env.setenv("DB2_PASSWORD", "pw-new")
    assert Settings(_env_file=None).db2_admin_password.get_secret_value() == "pw-new"


def test_a_missing_password_names_the_variable_judges_will_look_for(clean_env):
    with pytest.raises(ConfigError, match="DB2_PASSWORD"):
        Settings(_env_file=None).require("db2_admin_password")


def _fake_docker(running: set[str], ps: str = ""):
    def run(args, stdin=None):
        if args[:1] == ["inspect"]:
            name = args[-1]
            out = "true\n" if name in running else ""
            return subprocess.CompletedProcess(args, 0 if name in running else 1, out, "")
        if args[:1] == ["ps"]:
            return subprocess.CompletedProcess(args, 0, ps, "")
        raise AssertionError(args)
    return run


@pytest.mark.parametrize("running, ps, want", [
    ({"asof-db2"}, "", "asof-db2"),                                   # path C: compose
    ({"db2server"}, "", "db2server"),                                 # path A or B: extension or IBM image
    (set(), "mydb2\ticr.io/db2_community/db2:12.1.5.0\nweb\tnginx", "mydb2"),  # any single Db2 container
    (set(), "a\ticr.io/db2_community/db2\nb\ticr.io/db2_community/db2", None),  # ambiguous: ask the user
    (set(), "web\tnginx", None),
])
def test_setup_finds_the_db2_container_on_every_path(monkeypatch, running, ps, want):
    monkeypatch.setattr(setup, "_docker", _fake_docker(running, ps))
    assert setup.find_db2_container("asof-db2") == want


def test_the_configured_container_wins_when_it_runs(monkeypatch):
    monkeypatch.setattr(setup, "_docker", _fake_docker({"custom", "db2server"}))
    assert setup.find_db2_container("custom") == "custom"
