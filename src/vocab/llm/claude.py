"""Claude word-list generation using structured outputs (needs ANTHROPIC_API_KEY)."""

import anthropic

from vocab.llm.prompts import SYSTEM_PROMPT, WordBatch, user_prompt
from vocab.models import GeneratedWord


class ClaudeProvider:
    def __init__(self, model: str, effort: str = "low", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic()

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt(n, topics, exclude, level)}],
            output_format=WordBatch,
            output_config={"effort": self.effort},
            # Server-side fallback: if the model declines, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined the word-list request: {response.stop_details}")
        if response.parsed_output is None:
            raise RuntimeError(f"No structured output returned (stop: {response.stop_reason})")
        return response.parsed_output.words
