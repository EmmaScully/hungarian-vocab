"""Word bank operations: choosing review words and applying test results."""

from datetime import date

from vocab import srs
from vocab.models import Bank, BankEntry, Card, ListIndex, TestResult, WordList

# Lower sorts first: failed words, then "needs practice", then seen-but-never-tested.
_REVIEW_PRIORITY = {"fail": 0, "practice": 1, None: 2}


def review_candidates(bank: Bank) -> list[BankEntry]:
    """Words that should come back: failed, needs practice, or shown but never tested."""
    candidates = [e for e in bank.words.values() if e.status in ("learning", "new")]
    return sorted(
        candidates,
        key=lambda e: (_REVIEW_PRIORITY[e.last_rating], -e.lapses, e.last_tested or e.first_seen),
    )


def pick_review(bank: Bank, k: int) -> list[BankEntry]:
    return review_candidates(bank)[: max(k, 0)]


def entry_to_card(entry: BankEntry, source: str = "review") -> Card:
    return Card(
        id=entry.id,
        front_en=entry.en,
        back_hu=entry.hu,
        word_ids=[entry.id],
        pos=entry.pos,
        example_en=entry.example_en,
        example_hu=entry.example_hu,
        source=source,
    )


def add_cards(bank: Bank, cards: list[Card], today: date) -> None:
    """Register new word cards in the bank (status "new" until tested)."""
    for card in cards:
        if card.type != "word" or card.id in bank.words:
            continue
        bank.words[card.id] = BankEntry(
            id=card.id,
            en=card.front_en,
            hu=card.back_hu,
            pos=card.pos,
            example_en=card.example_en,
            example_hu=card.example_hu,
            first_seen=today,
        )


def apply_result(bank: Bank, result: TestResult, word_list: WordList, today: date) -> bool:
    """Apply one test result to the bank. Idempotent: returns False if already applied."""
    if result.list_id in bank.applied_results:
        return False

    cards = {c.id: c for c in word_list.cards}
    for card_id, rating in result.ratings.items():
        card = cards.get(card_id)
        if card is None:
            continue
        for wid in card.word_ids:
            entry = bank.words.get(wid)
            if entry is not None and entry.status != "mastered":
                srs.apply_rating(entry, rating, result.list_id, today)

    bank.applied_results.append(result.list_id)
    return True


def apply_pending_results(
    bank: Bank, index: ListIndex, results: list[TestResult], load_list, today: date
) -> list[str]:
    """Apply every result not yet in the bank; update the list index. Returns applied list ids."""
    applied = []
    for result in results:
        word_list = load_list(result.list_id)
        if not apply_result(bank, result, word_list, today):
            continue
        applied.append(result.list_id)
        entry = index.get(result.list_id)
        if entry is not None:
            entry.tested = True
            entry.score = (
                result.score
                if result.score is not None
                else srs.score(list(result.ratings.values()))
            )
    return applied
