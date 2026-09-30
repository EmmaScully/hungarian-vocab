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
