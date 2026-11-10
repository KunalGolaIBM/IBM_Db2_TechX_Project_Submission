"""Make unit tests hermetic: ignore any local .env and any ambient credentials."""

import pytest

from civiclens.config import Settings

_AMBIENT = (
    "DB2_PASSWORD", "CIVICLENS_AUTH_TOKENS", "LLM_PROVIDER", "LLM_MODEL",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "WATSONX_APIKEY", "WATSONX_PROJECT_ID",
)  # fmt: skip


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in _AMBIENT:
        monkeypatch.delenv(name, raising=False)
