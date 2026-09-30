"""Spaced-repetition maths: a simplified SM-2 mapped onto three buttons.

Mirrors site/js/srs.js — keep the two in sync.

    fail      -> lapse, ease -0.20, interval reset to 1 day, status "learning"
    practice  -> ease -0.15, interval grows slowly,          status "learning"
    mastered  -> interval *= ease,                           status "mastered" (terminal:
                 mastered words are never put in a new list again)
"""

from datetime import date

from vocab.models import BankEntry, HistoryItem, Rating

MIN_EASE = 1.3
RATING_POINTS: dict[str, float] = {"fail": 0.0, "practice": 0.5, "mastered": 1.0}


def apply_rating(entry: BankEntry, rating: Rating, list_id: str, today: date) -> BankEntry:
    if rating == "fail":
        entry.lapses += 1
        entry.ease = max(MIN_EASE, entry.ease - 0.20)
        entry.interval_days = 1
        entry.status = "learning"
    elif rating == "practice":
        entry.ease = max(MIN_EASE, entry.ease - 0.15)
        entry.interval_days = max(1, round(entry.interval_days * 1.2))
        entry.status = "learning"
    else:
        entry.interval_days = max(7, round(max(entry.interval_days, 1) * entry.ease))
        entry.status = "mastered"
        entry.mastered_on = today

    entry.ease = round(entry.ease, 2)
    entry.last_rating = rating
    entry.last_tested = today
    entry.history.append(HistoryItem(date=today, list_id=list_id, rating=rating))
    return entry


def score(ratings: list[Rating]) -> float:
    """Set score in percent: mastered = 1, needs practice = 0.5, fail = 0."""
    if not ratings:
        return 0.0
    return round(100 * sum(RATING_POINTS[r] for r in ratings) / len(ratings), 1)
