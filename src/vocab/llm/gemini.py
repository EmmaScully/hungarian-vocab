"""Gemini word-list generation using JSON-schema structured output (needs GEMINI_API_KEY)."""

import os

from google import genai
from google.genai import types

from vocab.llm.prompts import SYSTEM_PROMPT, WordBatch, user_prompt
from vocab.models import GeneratedWord


class GeminiProvider:
    def __init__(self, model: str, client: genai.Client | None = None):
        self.model = model
        self.client = client or genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def generate_words(
        self, n: int, topics: list[str], exclude: list[str], level: str
    ) -> list[GeneratedWord]:
        response = self.client.models.generate_content(
            model=self.model,
            contents=user_prompt(n, topics, exclude, level),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=WordBatch,
            ),
        )
        parsed = response.parsed
        if isinstance(parsed, WordBatch):
            return parsed.words
        if response.text:
            return WordBatch.model_validate_json(response.text).words
        raise RuntimeError(f"Gemini returned no word list: {response.prompt_feedback}")
