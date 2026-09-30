from types import SimpleNamespace

from vocab.llm.gemini import GeminiProvider
from vocab.llm.prompts import WordBatch, user_prompt

WORD = {"en": "bread", "hu": "kenyér", "pos": "noun", "example_hu": "Kérek kenyeret.",
        "example_en": "I'd like some bread."}


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def _provider(response):
    models = FakeModels(response)
    return GeminiProvider("gemini-test", client=SimpleNamespace(models=models)), models


def test_gemini_uses_parsed_output_and_schema():
    provider, models = _provider(
        SimpleNamespace(parsed=WordBatch.model_validate({"words": [WORD]}), text=None)
    )
    words = provider.generate_words(1, ["food"], ["alma"], "A1")
    assert words[0].hu == "kenyér"
    assert models.kwargs["config"].response_schema is WordBatch
    assert "alma" in models.kwargs["contents"]


def test_gemini_falls_back_to_text_json():
    import json

    provider, _ = _provider(SimpleNamespace(parsed=None, text=json.dumps({"words": [WORD]})))
    assert provider.generate_words(1, [], [], "A1")[0].en == "bread"


def test_prompt_without_topics_asks_for_frequent_words():
    assert "most frequently used" in user_prompt(5, [], [], "A1")


class FlakyModels:
    """Fails with the given status codes, then succeeds; records which model each call used."""

    def __init__(self, codes):
        self.codes = list(codes)
        self.models = []

    def generate_content(self, model, **kwargs):
        from google.genai import errors

        self.models.append(model)
        if self.codes:
            code = self.codes.pop(0)
            raise errors.APIError(code, {"error": {"code": code, "message": "busy"}})
        return SimpleNamespace(parsed=WordBatch.model_validate({"words": [WORD]}), text=None)


def _flaky(codes, fallbacks):
    models = FlakyModels(codes)
    provider = GeminiProvider("main", fallback_models=fallbacks,
                              client=SimpleNamespace(models=models), sleep=lambda s: None)
    return provider, models


def test_gemini_retries_then_falls_back_to_next_model():
    provider, models = _flaky([503, 503, 503, 503, 429], ["backup"])
    assert provider.generate_words(1, [], [], "A1")[0].hu == "kenyér"
    assert models.models == ["main"] * 4 + ["backup"] * 2


def test_gemini_does_not_retry_client_errors():
    import pytest
    from google.genai import errors

    provider, models = _flaky([400], ["backup"])
    with pytest.raises(errors.APIError):
        provider.generate_words(1, [], [], "A1")
    assert models.models == ["main"]


def test_gemini_gives_up_after_all_models():
    import pytest

    provider, models = _flaky([503] * 8, ["backup"])
    with pytest.raises(RuntimeError, match="All Gemini models unavailable"):
        provider.generate_words(1, [], [], "A1")
    assert len(models.models) == 8
