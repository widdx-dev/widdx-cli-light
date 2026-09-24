"""Tests for core/providers/providers.py — AI provider system."""
from core.providers.providers import (
    create_provider, get_available_models,
    fetch_free_models, fetch_ollama_models,
    OpenCodeZenProvider, OllamaProvider,
    OpenAICompatibleProvider, DeepSeekProvider,
)


def _cfg(name: str, model: str = "", base_url: str = "") -> dict:
    return {"provider": {"name": name, "model": model, "base_url": base_url}}


class TestCreateProvider:

    def test_opencode_zen(self):
        p = create_provider(_cfg("opencode-zen"), raw=True)
        assert isinstance(p, OpenCodeZenProvider)

    def test_ollama(self):
        p = create_provider(_cfg("ollama"), raw=True)
        assert isinstance(p, OllamaProvider)

    def test_openai(self):
        p = create_provider(_cfg("openai", model="gpt-4"), raw=True)
        assert isinstance(p, OpenAICompatibleProvider)

    def test_deepseek(self):
        p = create_provider(_cfg("deepseek", model="deepseek-chat"), raw=True)
        assert isinstance(p, DeepSeekProvider)


class TestResolveModel:

    def test_explicit_model(self):
        p = create_provider(_cfg("opencode-zen", model="deepseek-v4-flash-free"), raw=True)
        assert p.model == "deepseek-v4-flash-free"

    def test_empty_model_has_default(self):
        p = create_provider(_cfg("opencode-zen"), raw=True)
        assert p.model, "Model should not be empty"


class TestGetAvailableModels:

    def test_returns_list(self):
        models = get_available_models("opencode-zen", "https://opencode.ai/zen/v1")
        assert isinstance(models, list)


class TestFetchFreeModels:

    def test_returns_list(self):
        models = fetch_free_models()
        assert isinstance(models, list)

    def test_contains_expected_models(self):
        models = fetch_free_models()
        model_set = set(models)
        common = {"deepseek-v4-flash-free", "deepseek-v3-free", "qwen2.5-72b-free"}
        found = common & model_set
        assert len(found) >= 1, f"Expected free models, got: {models[:5]}"


class TestOllamaModels:

    def test_returns_empty_when_not_running(self):
        models = fetch_ollama_models("http://localhost:11434")
        assert isinstance(models, list)


class TestProviderConfig:

    def test_custom_base_url(self):
        url = "http://custom-proxy:8080/v1"
        p = create_provider(_cfg("opencode-zen", base_url=url), raw=True)
        assert p.base_url == url

    def test_deepseek_model(self):
        p = create_provider(_cfg("deepseek", model="deepseek-chat"), raw=True)
        assert p.model, "DeepSeek should have a model"

    def test_ollama_with_explicit_url(self):
        url = "http://192.168.1.100:11434"
        p = create_provider(_cfg("ollama", base_url=url), raw=True)
        assert p.base_url == url
