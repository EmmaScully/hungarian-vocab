from datetime import date

from tests.conftest import make_entry
from vocab import srs

TODAY = date(2026, 10, 5)


def test_fail_resets_interval_and_counts_lapse():
    e = make_entry("kenyér", "bread", interval_days=10)
    srs.apply_rating(e, "fail", "2026-W40", TODAY)
    assert (e.status, e.lapses, e.interval_days, e.ease) == ("learning", 1, 1, 2.3)
    assert e.history[-1].rating == "fail" and e.last_tested == TODAY


def test_practice_lowers_ease_keeps_learning():
    e = make_entry("kenyér", "bread", interval_days=5)
    srs.apply_rating(e, "practice", "2026-W40", TODAY)
    assert (e.status, e.lapses, e.interval_days, e.ease) == ("learning", 0, 6, 2.35)


def test_mastered_is_terminal_status():
    e = make_entry("kenyér", "bread")
    srs.apply_rating(e, "mastered", "2026-W40", TODAY)
    assert e.status == "mastered" and e.mastered_on == TODAY and e.interval_days >= 7


def test_ease_floor():
    e = make_entry("kenyér", "bread", ease=1.35)
    srs.apply_rating(e, "fail", "2026-W40", TODAY)
    assert e.ease == srs.MIN_EASE


def test_score():
    assert srs.score(["mastered", "practice", "fail", "mastered"]) == 62.5
    assert srs.score([]) == 0.0
