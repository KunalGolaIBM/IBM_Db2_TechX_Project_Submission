from backend.app import config


def test_local_environment_loads_without_expanding_passwords(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("DB2_PASSWORD='literal${SECRET}#value'\nDB2_SCHEMA=FROM_FILE\n")
    monkeypatch.setattr(config, "ENV_FILE", env)
    monkeypatch.delenv("DB2_PASSWORD", raising=False)
    monkeypatch.setenv("DB2_SCHEMA", "FROM_PROCESS")

    settings = config.Settings.from_env()

    assert settings.db2.password == "literal${SECRET}#value"
    assert settings.db2.schema == "FROM_PROCESS"
    assert settings.db2.password not in repr(settings)
    # dotenv writes os.environ; register the key with monkeypatch for cleanup.
    monkeypatch.setenv("DB2_PASSWORD", "")
