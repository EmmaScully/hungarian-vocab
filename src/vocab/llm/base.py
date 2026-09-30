"""LLM provider interface. Add new providers (Gemini, OpenAI, local...) by implementing this."""

from typing import Protocol

from vocab.config import LLMConfig
from vocab.models import GeneratedWord


class LLMProvider(Protocol):
    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        """Return up to n new Hungarian words, avoiding everything in `exclude`."""
        ...


def get_provider(config: LLMConfig) -> LLMProvider:
    if config.provider == "claude":
        from vocab.llm.claude import ClaudeProvider

        return ClaudeProvider(model=config.model, effort=config.effort)
    if config.provider == "gemini":
        from vocab.llm.gemini import GeminiProvider

        return GeminiProvider(model=config.model)
    raise ValueError(f"Unknown LLM provider: {config.provider!r}")
