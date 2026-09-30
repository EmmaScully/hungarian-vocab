"""LLM provider interface. Add new providers (OpenAI, local...) by implementing this."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from vocab.config import LLMConfig
from vocab.models import GeneratedWord

T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        """Return the model's answer parsed into `schema`."""
        ...

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

        return GeminiProvider(model=config.model, fallback_models=config.fallback_models)
    raise ValueError(f"Unknown LLM provider: {config.provider!r}")
