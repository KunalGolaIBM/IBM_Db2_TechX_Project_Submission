"""Tests for the LLM settings model."""

import pytest

from parity.config import LlmSettings, load_llm_settings


def test_live_settings_validate():
    settings = LlmSettings(model="real-model", base_url="https://example.test", api_key="k")
    settings.validate()
    assert settings.is_replay_only is False
    settings.require_live()


def test_empty_model_rejected():
    settings = LlmSettings(model="", base_url="http://localhost", api_key="k")
    with pytest.raises(ValueError, match="PARITY_LLM_MODEL"):
        settings.validate()


def test_bad_base_url_rejected():
    settings = LlmSettings(model="m", base_url="localhost:8000", api_key="k")
    with pytest.raises(ValueError, match="PARITY_LLM_BASE_URL"):
        settings.validate()


def test_live_without_key_rejected():
    settings = LlmSettings(model="m", base_url="http://localhost", api_key="")
    assert settings.is_replay_only is True
    with pytest.raises(ValueError, match="API key is required"):
        settings.require_live()


def test_load_llm_settings_from_env(monkeypatch):
    monkeypatch.setenv("PARITY_LLM_MODEL", "my-model")
    monkeypatch.setenv("PARITY_LLM_BASE_URL", "https://api.example")
    monkeypatch.setenv("PARITY_LLM_API_KEY", "secret")
    settings = load_llm_settings()
    assert settings.model == "my-model"
    assert settings.base_url == "https://api.example"
    assert settings.api_key == "secret"
    assert settings.is_replay_only is False


def test_load_llm_settings_rejects_bad_url(monkeypatch):
    monkeypatch.setenv("PARITY_LLM_BASE_URL", "not a url")
    with pytest.raises(ValueError, match="PARITY_LLM_BASE_URL"):
        load_llm_settings()
