from datetime import date

import pytest

from vocab.models import Bank, BankEntry, GeneratedWord, word_id


class FakeLLM:
    """Returns words from a fixed pool, recording each call."""

    def __init__(self, pool: list[tuple[str, str]]):
        self.pool = [
            GeneratedWord(en=en, hu=hu, pos="noun", example_hu=f"{hu}.", example_en=f"{en}.")
            for en, hu in pool
        ]
        self.calls: list[dict] = []

    def generate_words(self, n, topics, exclude, level):
        self.calls.append({"n": n, "topics": topics, "exclude": list(exclude)})
        start = sum(c["n"] for c in self.calls[:-1])
        return self.pool[start : start + n]


def make_entry(hu: str, en: str, **kw) -> BankEntry:
    kw.setdefault("first_seen", date(2026, 9, 1))
    return BankEntry(id=word_id(hu), hu=hu, en=en, **kw)


@pytest.fixture
def bank() -> Bank:
    entries = [
        make_entry("alma", "apple", status="mastered", last_rating="mastered"),
        make_entry("kutya", "dog", status="learning", last_rating="practice", lapses=0),
        make_entry("macska", "cat", status="learning", last_rating="fail", lapses=1),
        make_entry("ház", "house", status="learning", last_rating="fail", lapses=3),
        make_entry("víz", "water", status="new"),
    ]
    return Bank(words={e.id: e for e in entries})
