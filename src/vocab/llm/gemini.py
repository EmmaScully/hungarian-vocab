"""Gemini word-list generation using JSON-schema structured output (needs GEMINI_API_KEY)."""

import os
import time

from google import genai
from google.genai import errors, types

from vocab.llm.prompts import SYSTEM_PROMPT, WordBatch, user_prompt
from vocab.models import GeneratedWord

# Overloaded (503) or rate-limited (429) responses are usually temporary.
RETRYABLE_CODES = {429, 500, 503, 504}
RETRY_DELAYS = (10, 30, 60)  # seconds between attempts on the same model


class GeminiProvider:
    def __init__(
        self,
        model: str,
        fallback_models: list[str] | None = None,
        client: genai.Client | None = None,
        sleep=time.sleep,
    ):
        self.models = [model, *(fallback_models or [])]
        self.client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.sleep = sleep

    def _call(self, model: str, prompt: str):
        return self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=WordBatch,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    def _call_with_retries(self, prompt: str):
        """Retry transient errors with backoff, then move on to the next fallback model."""
        last_error: errors.APIError | None = None
        for model in self.models:
            for delay in (*RETRY_DELAYS, None):
                try:
                    return self._call(model, prompt)
                except errors.APIError as e:
                    if e.code not in RETRYABLE_CODES:
                        raise
                    last_error = e
                    if delay is None:
                        print(f"Gemini {model} unavailable ({e.code}); trying next model")
                    else:
                        print(f"Gemini {model} returned {e.code}; retrying in {delay}s")
                        self.sleep(delay)
        raise RuntimeError(f"All Gemini models unavailable: {self.models}") from last_error

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        response = self._call_with_retries(user_prompt(n, topics, exclude, level))
        parsed = response.parsed
        if isinstance(parsed, WordBatch):
            return parsed.words
        if response.text:
            return WordBatch.model_validate_json(response.text).words
        raise RuntimeError(f"Gemini returned no word list: {response.prompt_feedback}")
