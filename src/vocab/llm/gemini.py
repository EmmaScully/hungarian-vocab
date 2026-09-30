"""Gemini generation using JSON-schema structured output (needs GEMINI_API_KEY)."""

import os
import time
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from vocab.llm.prompts import SYSTEM_PROMPT, WordBatch, user_prompt
from vocab.models import GeneratedWord

T = TypeVar("T", bound=BaseModel)

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

    def _call(self, model: str, system: str, prompt: str, schema: type[BaseModel]):
        return self.client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

    def _call_with_retries(self, system: str, prompt: str, schema: type[BaseModel]):
        """Retry transient errors with backoff, then move on to the next fallback model."""
        last_error: errors.APIError | None = None
        for model in self.models:
            for delay in (*RETRY_DELAYS, None):
                try:
                    return self._call(model, system, prompt, schema)
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

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        response = self._call_with_retries(system, prompt, schema)
        if isinstance(response.parsed, schema):
            return response.parsed
        if response.text:
            return schema.model_validate_json(response.text)
        raise RuntimeError(f"Gemini returned no structured output: {response.prompt_feedback}")

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        prompt = user_prompt(n, topics, exclude, level)
        return self.generate_structured(SYSTEM_PROMPT, prompt, WordBatch).words
