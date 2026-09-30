"""Claude word-list generation using structured outputs."""

import anthropic
from pydantic import BaseModel

from vocab.models import GeneratedWord

SYSTEM_PROMPT = """\
You build vocabulary lists for a native English speaker learning Hungarian.

Rules for every word:
- Give the Hungarian word in dictionary form: nouns in nominative singular, verbs in \
3rd person singular present indefinite (the standard Hungarian dictionary form, e.g. "eszik", \
"megy"), adjectives in base form. Short fixed phrases are allowed when they are how the \
idea is normally expressed.
- Give the single most common English meaning, kept short. Add a brief disambiguation in \
brackets only when the English is ambiguous, e.g. "right (correct)".
- Use correct Hungarian spelling with all accents (á é í ó ö ő ú ü ű).
- The example sentence must be short, natural, and suited to the learner's level.
- Every word must be distinct from the others and from the excluded words, including \
inflected forms or near-synonyms that would be tested with the same English prompt."""


class _WordBatch(BaseModel):
    words: list[GeneratedWord]


class ClaudeProvider:
    def __init__(self, model: str, effort: str = "low", client: anthropic.Anthropic | None = None):
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic()

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        if topics:
            focus = "Focus on these topics: " + ", ".join(topics) + "."
        else:
            focus = (
                "No topic given: choose among the most frequently used Hungarian words in "
                "everyday conversation, mixing parts of speech."
            )
        excluded = ", ".join(exclude) if exclude else "(none)"
        prompt = (
            f"Generate exactly {n} Hungarian vocabulary words for a {level} learner.\n"
            f"{focus}\n\n"
            f"Do NOT include any of these already-known words:\n{excluded}"
        )

        response = self.client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=_WordBatch,
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
