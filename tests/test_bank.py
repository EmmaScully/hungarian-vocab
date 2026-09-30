from datetime import UTC, date, datetime

from vocab import bank as bank_ops
from vocab.models import ListIndex, ListIndexEntry, TestResult, WordList

TODAY = date(2026, 10, 5)


def test_review_order_fail_first_then_lapses_then_practice_then_untested(bank):
    ids = [e.id for e in bank_ops.review_candidates(bank)]
    assert ids == ["ház", "macska", "kutya", "víz"]


def test_mastered_never_reviewed(bank):
    assert "alma" not in [e.id for e in bank_ops.pick_review(bank, 100)]


def test_pick_review_limit(bank):
    assert len(bank_ops.pick_review(bank, 2)) == 2
    assert bank_ops.pick_review(bank, 0) == []


def _word_list(bank, ids):
    cards = [bank_ops.entry_to_card(bank.words[i]) for i in ids]
    return WordList(id="2026-W40", created=datetime(2026, 9, 28, tzinfo=UTC), cards=cards)


def test_apply_result_updates_entries_and_is_idempotent(bank):
    wl = _word_list(bank, ["kutya", "víz", "alma"])
    result = TestResult(
        list_id="2026-W40",
        completed_at=datetime(2026, 10, 4, tzinfo=UTC),
        ratings={"kutya": "mastered", "víz": "fail", "alma": "fail"},
    )
    assert bank_ops.apply_result(bank, result, wl, TODAY)
    assert bank.words["kutya"].status == "mastered"
    assert bank.words["víz"].status == "learning" and bank.words["víz"].lapses == 1
    # Mastered words are frozen: a stray rating must not resurrect them.
    assert bank.words["alma"].status == "mastered" and bank.words["alma"].history == []

    history_len = len(bank.words["víz"].history)
    assert not bank_ops.apply_result(bank, result, wl, TODAY)
    assert len(bank.words["víz"].history) == history_len


def test_apply_pending_results_updates_index_score(bank):
    wl = _word_list(bank, ["kutya", "víz"])
    index = ListIndex(
        lists=[ListIndexEntry(id="2026-W40", created=wl.created, n_cards=2)]
    )
    result = TestResult(
        list_id="2026-W40",
        completed_at=datetime(2026, 10, 4, tzinfo=UTC),
        ratings={"kutya": "mastered", "víz": "practice"},
    )
    applied = bank_ops.apply_pending_results(bank, index, [result], lambda _: wl, TODAY)
    assert applied == ["2026-W40"]
    assert index.lists[0].tested and index.lists[0].score == 75.0
