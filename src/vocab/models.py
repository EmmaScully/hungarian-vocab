"""Data model shared by the Python pipeline and the static site (as JSON files in data/)."""

import unicodedata
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Rating = Literal["fail", "practice", "mastered"]
Status = Literal["new", "learning", "mastered"]
CardType = Literal["word", "sentence"]


def word_id(hu: str) -> str:
    """Stable id for a word: NFC-normalised, lowercased, whitespace-collapsed Hungarian lemma."""
    return " ".join(unicodedata.normalize("NFC", hu).lower().split())


class GeneratedWord(BaseModel):
    """One word as returned by the LLM."""

    en: str = Field(description="English translation (short, most common meaning)")
    hu: str = Field(description="Hungarian word in dictionary form")
    pos: str = Field(description="Part of speech, e.g. noun, verb, adjective, adverb, phrase")
    example_hu: str = Field(description="Short, simple Hungarian example sentence using the word")
    example_en: str = Field(description="English translation of the example sentence")


class GeneratedSentence(BaseModel):
    """One practice sentence as returned by the LLM."""

    en: str = Field(description="Natural English sentence")
    hu: str = Field(description="Natural Hungarian translation of the sentence")
    words_used: list[str] = Field(
        description="The list words this sentence uses, copied exactly as given in the list"
    )


class Card(BaseModel):
    """A flashcard. `type="sentence"` is reserved for the sentence-practice extension."""

    id: str
    type: CardType = "word"
    front_en: str
    back_hu: str
    word_ids: list[str]
    pos: str | None = None
    example_en: str | None = None
    example_hu: str | None = None
    source: Literal["new", "review"] = "new"


class WordList(BaseModel):
    id: str  # ISO week, e.g. "2026-W40"
    created: datetime
    topics: list[str] = []
    cards: list[Card]
    audio_url: str | None = None
    # Test-only sentence cards built from this list's words. Rated in the test for personal
    # information only: they never change the word bank.
    sentences: list[Card] = []


class ListIndexEntry(BaseModel):
    id: str
    created: datetime
    topics: list[str] = []
    n_cards: int
    audio_url: str | None = None
    audio_bytes: int | None = None
    audio_duration_s: float | None = None
    tested: bool = False
    score: float | None = None
    sentence_score: float | None = None
    has_writing: bool = False
    writing_submitted: bool = False
    writing_graded: bool = False


class ListIndex(BaseModel):
    lists: list[ListIndexEntry] = []

    def get(self, list_id: str) -> ListIndexEntry | None:
        return next((e for e in self.lists if e.id == list_id), None)


class HistoryItem(BaseModel):
    date: date
    list_id: str
    rating: Rating


class BankEntry(BaseModel):
    id: str
    en: str
    hu: str
    pos: str | None = None
    example_en: str | None = None
    example_hu: str | None = None
    status: Status = "new"
    ease: float = 2.5
    interval_days: int = 0
    lapses: int = 0
    last_rating: Rating | None = None
    first_seen: date
    last_tested: date | None = None
    mastered_on: date | None = None
    history: list[HistoryItem] = []


class Bank(BaseModel):
    version: int = 1
    applied_results: list[str] = []
    words: dict[str, BankEntry] = {}


class TestResult(BaseModel):
    """Written by the site's test mode to data/results/<list_id>-test.json."""

    __test__ = False  # not a pytest test class

    list_id: str
    completed_at: datetime
    ratings: dict[str, Rating]  # word card id -> FIRST rating given in the test
    score: float | None = None
    # Sentence cards: recorded for the dashboard only, never applied to the word bank.
    sentence_ratings: dict[str, Rating] = {}
    sentence_score: float | None = None
