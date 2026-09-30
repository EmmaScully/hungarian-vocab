"""Build a weekly word list: review words from the bank plus new LLM-generated words."""

from datetime import UTC, date, datetime

from vocab.bank import add_cards, entry_to_card, pick_review
from vocab.llm.base import LLMProvider
from vocab.models import Bank, Card, GeneratedWord, WordList, word_id

MAX_LLM_ATTEMPTS = 3


def iso_week_id(d: date) -> str:
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def generated_to_card(word: GeneratedWord) -> Card:
    return Card(
        id=word_id(word.hu),
        front_en=word.en.strip(),
        back_hu=word.hu.strip(),
        word_ids=[word_id(word.hu)],
        pos=word.pos,
        example_en=word.example_en,
        example_hu=word.example_hu,
        source="new",
    )


def new_cards(
    llm: LLMProvider, bank: Bank, need: int, topics: list[str], level: str
) -> list[Card]:
    """Ask the LLM for `need` words not already in the bank, topping up if it comes back short."""
    known_ids = set(bank.words)
    known_en = {e.en.lower() for e in bank.words.values()}
    exclude = sorted(e.hu for e in bank.words.values())
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


def build_list(
    bank: Bank,
    llm: LLMProvider,
    n: int,
    topics: list[str],
    review_ratio: float,
    level: str,
    now: datetime | None = None,
) -> WordList:
    """Create the list and register its new words in the bank (mutates `bank`)."""
    now = now or datetime.now(UTC)
    reviews = [entry_to_card(e) for e in pick_review(bank, int(n * review_ratio))]
    fresh = new_cards(llm, bank, n - len(reviews), topics, level)
    add_cards(bank, fresh, now.date())
    return WordList(id=iso_week_id(now.date()), created=now, topics=topics, cards=reviews + fresh)
