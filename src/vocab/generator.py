"""Build a weekly word list: lesson words, review words from the bank, then new LLM words."""

from datetime import UTC, date, datetime

from vocab.bank import add_cards, entry_to_card, pick_review
from vocab.llm.base import LLMProvider
from vocab.models import Bank, Card, GeneratedWord, WordList, word_id

MAX_LLM_ATTEMPTS = 3


def iso_week_id(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def generated_to_card(word: GeneratedWord, source: str = "new") -> Card:
    return Card(
        id=word_id(word.hu),
        front_en=word.en.strip(),
        back_hu=word.hu.strip(),
        word_ids=[word_id(word.hu)],
        pos=word.pos,
        example_en=word.example_en,
        example_hu=word.example_hu,
        source=source,
    )


def new_cards(
    llm: LLMProvider, bank: Bank, need: int, topics: list[str], level: str,
    also_exclude: list[Card] = (),
) -> list[Card]:
    """Ask the LLM for `need` words not already in the bank, topping up if it comes back short."""
    if need <= 0:
        return []
    known_ids = set(bank.words) | {c.id for c in also_exclude}
    known_en = {e.en.lower() for e in bank.words.values()} | {
        c.front_en.lower() for c in also_exclude
    }
    exclude = sorted({e.hu for e in bank.words.values()} | {c.back_hu for c in also_exclude})
    cards: list[Card] = []

    for _ in range(MAX_LLM_ATTEMPTS):
        missing = need - len(cards)
        if missing <= 0:
            break
        # Ask for a few extra to absorb duplicates.
        words = llm.generate_words(missing + 3, topics, exclude, level)
        for word in words:
            card = generated_to_card(word)
            if card.id in known_ids or card.front_en.lower() in known_en:
                continue
            cards.append(card)
            known_ids.add(card.id)
            known_en.add(card.front_en.lower())
            exclude.append(card.back_hu)
            if len(cards) == need:
                break
    return cards


def lesson_cards(bank: Bank, words: list[GeneratedWord]) -> list[Card]:
    """Cards for words from the tutoring lesson. Mastered words are still skipped."""
    cards: list[Card] = []
    seen: set[str] = set()
    for word in words:
        card = generated_to_card(word, source="lesson")
        entry = bank.words.get(card.id)
        if card.id in seen or (entry is not None and entry.status == "mastered"):
            continue
        seen.add(card.id)
        cards.append(card)
    return cards


def build_list(
    bank: Bank,
    llm: LLMProvider,
    n: int,
    topics: list[str],
    review_ratio: float,
    level: str,
    now: datetime | None = None,
    lesson_words: list[GeneratedWord] | None = None,
) -> WordList:
    """Create the list and register its new words in the bank (mutates `bank`).

    Lesson words always go in (so the list can be longer than n), then review words (up to
    review_ratio * n), then new LLM words to fill up to n.
    """
    now = now or datetime.now(UTC)
    lesson = lesson_cards(bank, lesson_words or [])
    taken = {c.id for c in lesson}
    reviews = [
        entry_to_card(e)
        for e in pick_review(bank, int(n * review_ratio) + len(taken))
        if e.id not in taken
    ][: int(n * review_ratio)]
    fresh = new_cards(
        llm, bank, n - len(lesson) - len(reviews), topics, level, also_exclude=lesson
    )
    add_cards(bank, lesson + fresh, now.date())
    return WordList(
        id=iso_week_id(now.date()), created=now, topics=topics, cards=lesson + reviews + fresh
    )
