"""Test-only practice sentences built from a list's words.

Sentence cards are shown in the end-of-week test next to the word cards. Their ratings are
recorded for the dashboard only — they never change the word bank.
"""

from pydantic import BaseModel

from vocab.llm.base import LLMProvider
from vocab.models import Card, GeneratedSentence, WordList, word_id

SENTENCE_SYSTEM = """\
You write short practice sentences for a native English speaker learning Hungarian.
- Each sentence uses one to three words from the given list, inflected naturally as \
Hungarian grammar requires.
- Sentences are natural, everyday and short (roughly 5–12 words), at about CEFR A2–B1.
- Give an accurate, natural English translation for each.
- Use correct Hungarian spelling with all accents.
- Spread the sentences across as many different list words as possible."""


class SentenceBatch(BaseModel):
    sentences: list[GeneratedSentence]


def sentence_prompt(word_list: WordList, n: int) -> str:
    words = "\n".join(f"- {c.back_hu} ({c.front_en})" for c in word_list.cards)
    return (
        f"Write exactly {n} practice sentences using words from this list.\n"
        f"In `words_used`, copy the list words exactly as written below.\n\n{words}"
    )


def generate_sentences(
    llm: LLMProvider, word_list: WordList, n: int, lesson: list[GeneratedSentence] = ()
) -> list[Card]:
    """Lesson sentences (all of them) first, then generated sentences to fill up to n."""
    known = {c.id for c in word_list.cards}
    cards: list[Card] = []
    seen: set[str] = set()
    need = n - len(lesson)
    generated = []
    if need > 0 and word_list.cards:
        prompt = sentence_prompt(word_list, need)
        generated = llm.generate_structured(SENTENCE_SYSTEM, prompt, SentenceBatch).sentences
    limit = len(lesson) + max(need, 0)
    tagged = [(s, "lesson") for s in lesson] + [(s, "new") for s in generated]
    for sentence, source in tagged:
        en, hu = sentence.en.strip(), sentence.hu.strip()
        if not en or not hu or hu.lower() in seen:
            continue
        seen.add(hu.lower())
        cards.append(
            Card(
                id=f"s{len(cards) + 1}",
                type="sentence",
                front_en=en,
                back_hu=hu,
                word_ids=[w for w in map(word_id, sentence.words_used) if w in known],
                source=source,
            )
        )
        if len(cards) == limit:
            break
    return cards
