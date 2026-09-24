"""Tests for core/providers/providers.py — AI provider system."""
from core.providers.providers import (
    create_provider, get_available_models,
    fetch_free_models, fetch_ollama_models,
    OpenCodeZenProvider, OllamaProvider,
    OpenAICompatibleProvider, DeepSeekProvider,
    AtriaProvider,
)


def _cfg(name: str, model: str = "", base_url: str = "") -> dict:
    return {"provider": {"name": name, "model": model, "base_url": base_url}}


class _FakeResponse:
    """Minimal response stand-in for exercising _describe_error offline."""

    def __init__(self, status: int, headers: dict | None = None, body: bytes = b""):
        self.status_code = status
        self.headers = headers or {}
        self._body = body

    def read(self) -> bytes:
        return self._body


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

    def test_atria(self):
        p = create_provider(_cfg("atria"), raw=True)
        assert isinstance(p, AtriaProvider)


class TestAtriaProvider:
    """Atria Dawn Preview — endpoint, model id, and error translation."""

    def test_defaults(self):
        p = AtriaProvider()
        assert p.name == "atria"
        assert p.model == "Atria-Dawn-Preview", "model id capitalization is significant"
        assert p.base_url == "https://api.atria-asi.ai/v1"
        assert AtriaProvider.CONTEXT_WINDOW == 256_000

    def test_explicit_model_preserved(self):
        p = AtriaProvider(model="Atria-Dawn-Preview")
        assert p.model == "Atria-Dawn-Preview"

    def test_is_openai_compatible(self):
        assert isinstance(AtriaProvider(), OpenAICompatibleProvider)

    def test_available_models(self):
        assert "Atria-Dawn-Preview" in get_available_models("atria")

    def test_error_401_invalid_key(self):
        p = AtriaProvider(api_key="atr_somekey")
        msg = p._describe_error(_FakeResponse(401))
        assert "invalid or revoked" in msg

    def test_error_401_missing_key(self):
        p = AtriaProvider(api_key="")
        assert "No API key" in p._describe_error(_FakeResponse(401))

    def test_error_401_wrong_key_prefix(self):
        p = AtriaProvider(api_key="sk-wrongprefix")
        msg = p._describe_error(_FakeResponse(401))
        assert "atr_" in msg

    def test_error_429_surfaces_retry_headers(self):
        headers = {"Retry-After": "42", "x-rpm-limit": "60", "x-rpm-remaining": "0"}
        msg = AtriaProvider()._describe_error(_FakeResponse(429, headers))
        assert "429" in msg
        assert "42s" in msg, "Retry-After should be surfaced"
        assert "0/60" in msg, "remaining/limit should be surfaced"

    def test_error_5xx_is_retryable_hint(self):
        msg = AtriaProvider()._describe_error(_FakeResponse(503, body=b"upstream"))
        assert "temporarily unavailable" in msg

    def test_error_generic_includes_body(self):
        msg = AtriaProvider()._describe_error(_FakeResponse(400, body=b'{"error":"bad"}'))
        assert "400" in msg and "bad" in msg

    def test_thinking_tags_split_out(self):
        text = '[thinking]\nsecret reasoning\n[/thinking]\n\nOK'
        reasoning, content = AtriaProvider._split_thinking(text)
        assert reasoning == ["secret reasoning"]
        assert content == "OK", "answer must not repeat the scratchpad"

    def test_think_angle_tags_split_out(self):
        reasoning, content = AtriaProvider._split_thinking("<think>mid thought</think>Answer")
        assert reasoning == ["mid thought"]
        assert content == "Answer"

    def test_reasoning_bracket_tags_split_out(self):
        reasoning, content = AtriaProvider._split_thinking("[reasoning]step 1[/reasoning]Answer")
        assert reasoning == ["step 1"]
        assert content == "Answer"

    def test_plain_text_untouched(self):
        reasoning, content = AtriaProvider._split_thinking("Plain answer")
        assert reasoning == []
        assert content == "Plain answer"

    def test_thinking_only_yields_empty_answer(self):
        reasoning, content = AtriaProvider._split_thinking("<think>all reasoning</think>")
        assert reasoning == ["all reasoning"]
        assert content == ""

    def test_key_prefix_constant(self):
        assert AtriaProvider.KEY_PREFIX == "atr_"
        assert AtriaProvider.MODEL == "Atria-Dawn-Preview"
        assert AtriaProvider.MAX_OUTPUT_TOKENS == 65_536


class TestAtriaKeyResolution:
    """Atria keys are often exported as the spaced "ATRIA API KEY" form."""

    def test_reads_spaced_env_var(self, monkeypatch):
        from core.config import keychain

        monkeypatch.delenv("ATRIA_API_KEY", raising=False)
        monkeypatch.setenv("ATRIA API KEY", "atr_spaced_value")
        monkeypatch.setattr(keychain, "_KEY_PROVIDERS", {}, raising=False)
        monkeypatch.setattr(keychain, "_load_persisted_keys", lambda: {}, raising=False)
        assert keychain.get_key("atria") == "atr_spaced_value"

    def test_underscore_form_takes_priority(self, monkeypatch):
        from core.config import keychain

        monkeypatch.setenv("ATRIA_API_KEY", "atr_canonical")
        monkeypatch.setenv("ATRIA API KEY", "atr_spaced")
        monkeypatch.setattr(keychain, "_KEY_PROVIDERS", {}, raising=False)
        monkeypatch.setattr(keychain, "_load_persisted_keys", lambda: {}, raising=False)
        assert keychain.get_key("atria") == "atr_canonical"


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
