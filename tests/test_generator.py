from datetime import UTC, date, datetime

from tests.conftest import FakeLLM
from vocab.generator import build_list, iso_week_id
from vocab.models import Bank, WordList

NOW = datetime(2026, 9, 28, 6, 0, tzinfo=UTC)


def test_iso_week_id():
    assert iso_week_id(date(2026, 9, 28)) == "2026-W40"
    assert iso_week_id(date(2027, 1, 1)) == "2026-W53"


def test_list_mixes_review_and_new(bank):
    llm = FakeLLM([("bread", "kenyér"), ("milk", "tej"), ("egg", "tojás"), ("salt", "só")])
    wl = build_list(bank, llm, n=4, topics=["food"], review_ratio=0.5, level="A1", now=NOW)

    assert wl.id == "2026-W40"
    assert [c.source for c in wl.cards] == ["review", "review", "new", "new"]
    assert [c.id for c in wl.cards[:2]] == ["ház", "macska"]
    assert "alma" not in [c.id for c in wl.cards]
    # Every bank word, mastered included, is excluded from generation.
    assert {"alma", "kutya", "víz"} <= set(llm.calls[0]["exclude"])
    assert llm.calls[0]["topics"] == ["food"]
    # New words are registered as untested.
    assert bank.words["kenyér"].status == "new"


def test_duplicates_are_dropped_and_topped_up(bank):
    llm = FakeLLM(
        [("apple", "Alma"), ("dog", "kutya"), ("bread", "kenyér"), ("bread", "Kenyér"),
         ("milk", "tej"), ("egg", "tojás"), ("salt", "só"), ("sugar", "cukor")]
    )
    wl = build_list(Bank(words={k: bank.words[k] for k in ("alma", "kutya")}), llm, n=3,
                    topics=[], review_ratio=0.5, level="A1", now=NOW)
    hu = [c.back_hu for c in wl.cards]
    assert hu[0] == "kutya"  # review
    assert hu[1:] == ["kenyér", "tej"]
    assert len({c.id for c in wl.cards}) == len(wl.cards)


def test_short_llm_output_triggers_retry():
    llm = FakeLLM([("bread", "kenyér")])
    wl = build_list(Bank(), llm, n=3, topics=[], review_ratio=0.5, level="A1", now=NOW)
    assert len(llm.calls) == 3  # MAX_LLM_ATTEMPTS
    assert len(wl.cards) == 1


def test_wordlist_json_roundtrip(bank):
    llm = FakeLLM([("bread", "kenyér"), ("milk", "tej")])
    wl = build_list(bank, llm, n=2, topics=[], review_ratio=0, level="A1", now=NOW)
    assert WordList.model_validate_json(wl.model_dump_json()) == wl
