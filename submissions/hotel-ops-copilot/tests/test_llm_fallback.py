"""The quota-aware model chain switches models on a daily-quota error and nothing else (no network)."""
import pytest

from hotelops import llm


class _Model:
    def __init__(self, name, fail):
        self.name, self.fail = name, fail

    def invoke(self, messages):
        if self.fail == "daily":
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Generate content requests per day limit exceeded")
        if self.fail == "other":
            raise ValueError("400 INVALID_ARGUMENT")
        return f"answer from {self.name}"


@pytest.fixture()
def chain(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "m1")
    monkeypatch.setenv("LLM_FALLBACK_MODELS", "m2,m3")
    llm._exhausted.clear()
    yield
    llm._exhausted.clear()


def test_switches_to_next_model_on_daily_quota(chain, monkeypatch):
    models = {"m1": _Model("m1", "daily"), "m2": _Model("m2", None), "m3": _Model("m3", None)}
    monkeypatch.setattr(llm, "get_chat_model", lambda name=None: models[name])
    switches = []
    assert llm.invoke_llm(lambda m: m, [], lambda a, b: switches.append((a, b))) == "answer from m2"
    assert switches == [("m1", "m2")] and llm.active_model() == "m2"
    # sticky: the exhausted model is not tried again
    assert llm.invoke_llm(lambda m: m, []) == "answer from m2" and switches == [("m1", "m2")]


def test_other_errors_are_not_swallowed(chain, monkeypatch):
    monkeypatch.setattr(llm, "get_chat_model", lambda name=None: _Model(name, "other"))
    with pytest.raises(ValueError):
        llm.invoke_llm(lambda m: m, [])
    assert not llm._exhausted


def test_all_models_exhausted_raises_with_friendly_message(chain, monkeypatch):
    monkeypatch.setattr(llm, "get_chat_model", lambda name=None: _Model(name, "daily"))
    with pytest.raises(RuntimeError) as err:
        llm.invoke_llm(lambda m: m, [])
    assert "daily free-tier quota" in llm.friendly_llm_error(err.value)


def test_transient_errors_retry_on_the_same_model(chain, monkeypatch):
    calls = {"n": 0}

    class Flaky:
        def invoke(self, messages):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("503 UNAVAILABLE: model overloaded")
            return "recovered"

    monkeypatch.setattr(llm, "get_chat_model", lambda name=None: Flaky())
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.invoke_llm(lambda m: m, []) == "recovered" and calls["n"] == 2
    assert not llm._exhausted
