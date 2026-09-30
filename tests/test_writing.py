import json
from datetime import UTC, datetime

import pytest
from cryptography.exceptions import InvalidTag

from vocab import crypto
from vocab.bank import apply_result
from vocab.models import Bank, BankEntry, Card, GeneratedSentence, ListIndex, TestResult, WordList
from vocab.sentences import SentenceBatch, generate_sentences
from vocab.writing import (
    AnswerFeedback,
    Correction,
    Feedback,
    GeneratedExercise,
    GlossaryItem,
    ReadingQuestion,
    Submission,
    WritingFeedback,
    WritingPrompt,
    WritingStore,
    feedback_email_html,
    generate_exercise,
    grade,
    grading_prompt,
)

NOW = datetime(2026, 9, 28, 6, tzinfo=UTC)
WL = WordList(
    id="2026-W40",
    created=NOW,
    cards=[
        Card(id="madár", front_en="bird", back_hu="madár", word_ids=["madár"]),
        Card(id="repülni", front_en="to fly", back_hu="repülni", word_ids=["repülni"]),
    ],
)

EXERCISE = GeneratedExercise(
    title_hu="A madarak", title_en="Birds", theme="birdwatching",
    passage_hu="Első bekezdés.\n\nMásodik bekezdés.",
    glossary=[GlossaryItem(hu="fészek", en="nest")],
    questions=[
        ReadingQuestion(kind="short", question_hu="Hol?", question_en="Where?"),
        ReadingQuestion(kind="long", question_hu="Miért?", question_en="Why?"),
    ],
    writing_prompts=[
        WritingPrompt(kind="short", prompt_hu="Írj!", prompt_en="Write!", min_words=40,
                      max_words=80),
    ],
)

FEEDBACK = Feedback(
    summary="Good <work>", level_estimate="B1", reading_score_pct=70, writing_score_pct=60,
    answers=[AnswerFeedback(question=1, verdict="correct", score=9, feedback="Nice",
                            model_answer_hu="A parkban.")],
    writing=[WritingFeedback(prompt=1, score=6, level_estimate="A2+", strengths=["clear"],
                             corrections=[Correction(original="madar", corrected="madár",
                                                     explanation="accent")],
                             improved_version_hu="Szia!", comments="Watch accents")],
    next_steps=["Practise accents"],
)


class FakeLLM:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def generate_structured(self, system, prompt, schema):
        self.calls.append((system, prompt, schema))
        return self.responses[schema]


def test_crypto_roundtrip_and_wrong_password():
    envelope = crypto.encrypt_json({"hu": "árvíztűrő tükörfúrógép"}, "correct horse")
    assert "árvíz" not in json.dumps(envelope)
    assert crypto.decrypt_json(envelope, "correct horse") == {"hu": "árvíztűrő tükörfúrógép"}
    with pytest.raises(InvalidTag):
        crypto.decrypt_json(envelope, "wrong")


def test_sentences_map_words_and_skip_duplicates():
    batch = SentenceBatch(sentences=[
        GeneratedSentence(en="The bird flies.", hu="A madár repül.",
                          words_used=["Madár", "repülni", "unknown"]),
        GeneratedSentence(en="Dup", hu="a madár repül.", words_used=[]),
        GeneratedSentence(en="I fly.", hu="Repülök.", words_used=["repülni"]),
    ])
    cards = generate_sentences(FakeLLM({SentenceBatch: batch}), WL, 5)
    assert [c.id for c in cards] == ["s1", "s2"]
    assert cards[0].type == "sentence" and cards[0].word_ids == ["madár", "repülni"]


def test_sentence_ratings_never_touch_the_bank():
    wl = WL.model_copy(update={"sentences": [
        Card(id="s1", type="sentence", front_en="x", back_hu="y", word_ids=["madár"])]})
    bank = Bank(words={"madár": BankEntry(id="madár", en="bird", hu="madár",
                                          first_seen=NOW.date())})
    result = TestResult(list_id="2026-W40", completed_at=NOW, ratings={},
                        sentence_ratings={"s1": "fail"})
    apply_result(bank, result, wl, NOW.date())
    assert bank.words["madár"].history == [] and bank.words["madár"].lapses == 0


def test_writing_store_encrypts_everything(tmp_path):
    llm = FakeLLM({GeneratedExercise: EXERCISE, Feedback: FEEDBACK})
    store = WritingStore(tmp_path, "pw")
    exercise = generate_exercise(llm, "2026-W40", WL, ListIndex(), ["cooking"])
    store.save_exercise(exercise)
    assert "madár" in llm.calls[0][1] and "cooking" in llm.calls[0][1]

    raw = store.exercise_path("2026-W40").read_text()
    assert "Első" not in raw and "madarak" not in raw
    assert store.load_exercise("2026-W40").title_hu == "A madarak"
    assert store.recent_themes() == ["birdwatching"]

    sub = Submission(week_id="2026-W40", submitted_at=NOW, answers={"q1": "A parkban."},
                     writing={"w1": "Szia madar"})
    store.submission_path("2026-W40").parent.mkdir(parents=True)
    store.submission_path("2026-W40").write_text(
        json.dumps(crypto.encrypt_json(sub.model_dump(mode="json"), "pw")))
    assert store.ungraded_weeks() == ["2026-W40"]

    prompt = grading_prompt(exercise, sub)
    assert "A parkban." in prompt and "(no answer)" in prompt and "2 words" in prompt
    feedback = grade(llm, exercise, sub)
    store.save_feedback(feedback)
    assert store.ungraded_weeks() == []
    assert store.load_feedback("2026-W40").reading_score_pct == 70

    html = feedback_email_html(exercise, sub, feedback)
    assert "Good &lt;work&gt;" in html and "madár" in html and "A parkban." in html
