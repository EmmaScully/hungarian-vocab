"""Prompts shared by every LLM provider."""

from pydantic import BaseModel

from vocab.models import GeneratedWord

SYSTEM_PROMPT = """\
You build vocabulary lists for a native English speaker learning Hungarian.

Rules for every word:
- Give the Hungarian word in its base form: nouns in nominative singular, adjectives in \
base form, and VERBS IN THE INFINITIVE (the -ni form, e.g. "enni", "menni", "repülni", \
"lélegezni") — never a conjugated form like "eszik". Short fixed phrases are allowed when \
they are how the idea is normally expressed.
- Give the single most common English meaning, kept short. English verbs are infinitives \
too ("to eat", "to fly"). Add a brief disambiguation in brackets only when the English is \
ambiguous, e.g. "right (correct)".
- Use correct Hungarian spelling with all accents (á é í ó ö ő ú ü ű).
- The example sentence must be short, natural, and suited to the learner's level.
- Every word must be distinct from the others and from the excluded words, including \
inflected forms or near-synonyms that would be tested with the same English prompt."""


class WordBatch(BaseModel):
    words: list[GeneratedWord]


def user_prompt(n: int, topics: list[str], exclude: list[str], level: str) -> str:
    if topics:
        focus = "Focus on these topics: " + ", ".join(topics) + "."
    else:
        focus = (
            "No topic given: choose among the most frequently used Hungarian words in "
            "everyday conversation, mixing parts of speech."
        )
    excluded = ", ".join(exclude) if exclude else "(none)"
    return (
        f"Generate exactly {n} Hungarian vocabulary words for a {level} learner.\n"
        f"{focus}\n\n"
        f"Do NOT include any of these already-known words:\n{excluded}"
    )
