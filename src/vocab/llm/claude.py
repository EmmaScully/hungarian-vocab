"""Claude generation using structured outputs (needs ANTHROPIC_API_KEY)."""

from typing import TypeVar

import anthropic
from pydantic import BaseModel

from vocab.llm.prompts import SYSTEM_PROMPT, WordBatch, user_prompt
from vocab.models import GeneratedWord

T = TypeVar("T", bound=BaseModel)


class ClaudeProvider:
    def __init__(self, model: str, effort: str = "low", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic()

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
            output_config={"effort": self.effort},
            # Server-side fallback: if the model declines, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the request: {response.stop_details}")
        if response.parsed_output is None:
            raise RuntimeError(f"No structured output returned (stop: {response.stop_reason})")
        return response.parsed_output

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        prompt = user_prompt(n, topics, exclude, level)
        return self.generate_structured(SYSTEM_PROMPT, prompt, WordBatch).words
