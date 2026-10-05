from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import FakeLLM
from vocab.cli import scheduled_run_due
from vocab.generator import build_list
from vocab.lesson import LessonNotes, LessonSentence, clean_chat, parse_lesson
from vocab.models import GeneratedSentence, GeneratedWord, WordList
from vocab.sentences import SentenceBatch, generate_sentences

CHAT = (Path(__file__).parent / "fixtures" / "lesson_chat.txt").read_text(encoding="utf-8")
EXPECTED = [
    "esett az eső",
    "jöttek",
    "hozzám",
    "Luke főzött tacost",
    "marhahús/tehénhús",
    "szor, -szer, -ször",
    "lelőni - to shoot down",
    "ez a hétvége kivételes volt. Ezen a hétvégén a szüleim mennek vacsorára. "
    "Semmi más nem lesz",
    "kivételes tehetség",
]
MEL = ZoneInfo("Australia/Melbourne")


def word(en, hu):
    return GeneratedWord(en=en, hu=hu, pos="noun", example_hu=f"{hu}.", example_en=f"{en}.")


@pytest.mark.parametrize(
    "paste",
    [CHAT, CHAT.replace("\n", ""), CHAT.replace("\n", " ")],
    ids=["as-pasted", "line-breaks-stripped", "line-breaks-to-spaces"],
)
def test_clean_chat_removes_metadata(paste):
    assert clean_chat(paste).splitlines() == EXPECTED


def test_parse_lesson_sends_cleaned_notes():
    class LLM:
        def generate_structured(self, system, prompt, schema):
            self.prompt = prompt
            return LessonNotes(topics=[], vocabulary=[], sentences=[], grammar_points=[])

    llm = LLM()
    parse_lesson(llm, CHAT)
    assert "Timea" not in llm.prompt and "18:3" not in llm.prompt and "img" not in llm.prompt
    assert "lelőni - to shoot down" in llm.prompt


def test_lesson_words_come_first_and_skip_mastered(bank):
    lesson = [word("brave", "bátor"), word("apple", "alma"), word("dog", "kutya"),
              word("brave", "Bátor")]
    llm = FakeLLM([("bread", "kenyér"), ("milk", "tej"), ("salt", "só")])
    wl = build_list(bank, llm, n=4, topics=["paintball"], review_ratio=0.5, level="A1",
                    now=datetime(2026, 10, 5, 8, tzinfo=UTC), lesson_words=lesson)
    assert [(c.id, c.source) for c in wl.cards] == [
        ("bátor", "lesson"),  # new lesson word
        ("kutya", "lesson"),  # already being practised: comes from the lesson, not review
        ("ház", "review"),    # reviews still added (up to review_ratio * n)
        ("macska", "review"),
    ]
    assert "alma" not in [c.id for c in wl.cards]  # mastered stays retired
    assert bank.words["bátor"].status == "new"
    assert llm.calls == []  # list already full, so no new words requested


def test_lesson_sentences_go_first():
    wl = WordList(id="2026-W41", created=datetime(2026, 10, 5, tzinfo=UTC), cards=[])
    lesson = [GeneratedSentence(en="It rained.", hu="Esett az eső.", words_used=[])]

    class LLM:
        def generate_structured(self, system, prompt, schema):
            raise AssertionError("no words to build sentences from")

    cards = generate_sentences(LLM(), wl, 10, lesson=lesson)
    assert [(c.back_hu, c.source) for c in cards] == [("Esett az eső.", "lesson")]


def test_generated_sentences_fill_up_to_n(bank):
    from vocab.bank import entry_to_card

    wl = WordList(id="2026-W41", created=datetime(2026, 10, 5, tzinfo=UTC),
                  cards=[entry_to_card(bank.words["kutya"])])
    batch = SentenceBatch(sentences=[
        GeneratedSentence(en=f"S{i}", hu=f"M{i}", words_used=["kutya"]) for i in range(5)])

    class LLM:
        def generate_structured(self, system, prompt, schema):
            assert "exactly 2" in prompt
            return batch

    lesson = [GeneratedSentence(en=s.en, hu=s.hu, words_used=[])
              for s in [LessonSentence(hu="Bátor vagyok.", en="I am brave.")]]
    cards = generate_sentences(LLM(), wl, 3, lesson=lesson)
    assert [c.source for c in cards] == ["lesson", "new", "new"]


@pytest.mark.parametrize(
    "local, due",
    [
        (datetime(2026, 10, 5, 20, 7, tzinfo=MEL), False),  # Monday before 21:00
        (datetime(2026, 10, 5, 21, 7, tzinfo=MEL), True),   # Monday after the deadline
        (datetime(2026, 10, 6, 0, 7, tzinfo=MEL), True),    # backup run past midnight
    ],
)
def test_scheduled_run_waits_for_deadline(local, due):
    assert scheduled_run_due(local, time(21, 0)) is due


def test_cron_times_hit_the_deadline_in_both_seasons():
    def local(utc_hour, utc_minute, day):
        return datetime(2026, *day, utc_hour, utc_minute, tzinfo=UTC).astimezone(MEL)

    # Daylight saving (AEDT): the 10:07 UTC run is at 21:07 local.
    assert local(10, 7, (10, 5)).strftime("%a %H:%M") == "Mon 21:07"
    # Winter (AEST): 10:07 UTC is 20:07 (too early); 11:07 UTC is 21:07.
    assert not scheduled_run_due(local(10, 7, (6, 1)), time(21, 0))
    assert local(11, 7, (6, 1)).strftime("%a %H:%M") == "Mon 21:07"
