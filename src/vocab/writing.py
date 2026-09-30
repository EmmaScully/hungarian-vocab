"""Weekly reading & writing exercise: generation, grading and feedback.

Everything here is private, so it is only ever committed encrypted (see vocab.crypto):
    data/writing/<week>.enc.json              exercise (passage, questions, writing prompts)
    data/writing/submissions/<week>.enc.json  answers, written by the site
    data/writing/feedback/<week>.enc.json     LLM feedback, shown in the site's Writing tab
Answers are keyed by position: "q1", "q2", ... for questions, "w1", "w2", ... for prompts.
"""

import json
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from vocab import crypto
from vocab.llm.base import LLMProvider
from vocab.models import ListIndex, WordList

# ---------- exercise ----------


class GlossaryItem(BaseModel):
    hu: str
    en: str


class ReadingQuestion(BaseModel):
    kind: Literal["short", "long"] = Field(
        description="short = one word to one sentence; long = a few sentences"
    )
    question_hu: str = Field(description="Question in Hungarian")
    question_en: str = Field(description="English translation of the question")


class WritingPrompt(BaseModel):
    kind: Literal["short", "long"]
    prompt_hu: str = Field(description="Writing task in Hungarian")
    prompt_en: str = Field(description="English translation of the task")
    min_words: int
    max_words: int


class GeneratedExercise(BaseModel):
    title_hu: str
    title_en: str
    theme: str = Field(description="The theme of the passage, in English, a few words")
    passage_hu: str = Field(description="The reading passage in Hungarian, in paragraphs")
    glossary: list[GlossaryItem] = Field(
        description="6-10 harder words from the passage with English meanings"
    )
    questions: list[ReadingQuestion]
    writing_prompts: list[WritingPrompt]


class WritingExercise(GeneratedExercise):
    week_id: str
    created: datetime
    level: str


EXERCISE_SYSTEM = """\
You are an experienced teacher of Hungarian as a foreign language, writing a weekly reading \
and writing exercise for a native English speaker.
- The passage is original, natural Hungarian at CEFR {level}: roughly 250–400 words in 3–5 \
paragraphs, with varied tenses and a few common idioms. Use correct spelling with all accents.
- Choose an engaging theme. Draw on the learner's recent vocabulary themes where it fits \
naturally, or pick a general-interest topic (culture, travel, food, nature, everyday life, \
Hungary). Don't repeat recent passage themes.
- Work in several words from the learner's current list where they fit naturally.
- Reading questions are in Hungarian with English translations: {n_short} short-answer \
questions (facts from the text) and {n_long} longer questions (inference, opinion or \
summary, answerable in a few sentences).
- Writing prompts are in Hungarian with English translations: one short task (40–80 words, \
e.g. a message or note) and one longer task (120–200 words, e.g. an opinion, story or \
letter), both related to the passage theme."""


def exercise_prompt(current: WordList | None, index: ListIndex, recent_themes: list[str]) -> str:
    topics = sorted({t for e in index.lists for t in e.topics})
    lines = []
    if current is not None:
        words = ", ".join(f"{c.back_hu} ({c.front_en})" for c in current.cards[:60])
        lines.append(f"Current word list ({current.id}): {words}")
    lines.append(f"Topics of the learner's word lists so far: {', '.join(topics) or '(none)'}")
    avoid = ", ".join(recent_themes) or "(none)"
    lines.append(f"Recent passage themes to avoid repeating: {avoid}")
    return "\n".join(lines)


def generate_exercise(
    llm: LLMProvider,
    week_id: str,
    current: WordList | None,
    index: ListIndex,
    recent_themes: list[str],
    level: str = "B1–B2",
    n_short: int = 4,
    n_long: int = 2,
) -> WritingExercise:
    system = EXERCISE_SYSTEM.format(level=level, n_short=n_short, n_long=n_long)
    generated = llm.generate_structured(
        system, exercise_prompt(current, index, recent_themes), GeneratedExercise
    )
    return WritingExercise(
        **generated.model_dump(), week_id=week_id, created=datetime.now(UTC), level=level
    )


# ---------- submission & feedback ----------


class Submission(BaseModel):
    week_id: str
    submitted_at: datetime
    answers: dict[str, str] = {}  # "q1" -> answer
    writing: dict[str, str] = {}  # "w1" -> text


class AnswerFeedback(BaseModel):
    question: int = Field(description="1-based question number")
    verdict: Literal["correct", "partly correct", "incorrect", "not answered"]
    score: int = Field(description="0-10")
    feedback: str = Field(description="Feedback in English, including language errors")
    model_answer_hu: str = Field(description="A good model answer in Hungarian")


class Correction(BaseModel):
    original: str = Field(description="The learner's phrase, quoted exactly")
    corrected: str = Field(description="Corrected Hungarian")
    explanation: str = Field(description="Short explanation in English")


class WritingFeedback(BaseModel):
    prompt: int = Field(description="1-based writing prompt number")
    score: int = Field(description="0-10")
    level_estimate: str = Field(description="Estimated CEFR level of this piece")
    strengths: list[str] = Field(description="What went well, in English")
    corrections: list[Correction]
    improved_version_hu: str = Field(description="A corrected, natural version of the text")
    comments: str = Field(description="Overall comments in English")


class Feedback(BaseModel):
    summary: str = Field(description="Encouraging overall summary in English, 3-5 sentences")
    level_estimate: str = Field(description="Overall CEFR estimate")
    reading_score_pct: int = Field(description="Reading comprehension score, 0-100")
    writing_score_pct: int = Field(description="Writing score, 0-100")
    answers: list[AnswerFeedback]
    writing: list[WritingFeedback]
    next_steps: list[str] = Field(description="2-4 concrete things to practise next, in English")


class GradedFeedback(Feedback):
    week_id: str
    graded_at: datetime


GRADING_SYSTEM = """\
You are an experienced, encouraging teacher of Hungarian marking a learner's weekly reading \
and writing exercise. Write ALL feedback and explanations in English; model answers and \
corrected texts are in Hungarian.
- Reading answers: judge comprehension first, then language accuracy. Mark blank answers as \
"not answered" with score 0. Answers may be in Hungarian or English; note if the learner \
used English.
- Writing: list the most important grammar, spelling (including accents), word-order and \
vocabulary errors, quoting the learner's words exactly, with corrections and brief \
explanations. Keep an eye on the task's word range.
- Be specific and constructive; don't invent errors."""


def grading_prompt(exercise: WritingExercise, submission: Submission) -> str:
    parts = [f"PASSAGE ({exercise.title_hu}):\n{exercise.passage_hu}", "READING QUESTIONS:"]
    for i, q in enumerate(exercise.questions, 1):
        answer = submission.answers.get(f"q{i}", "").strip() or "(no answer)"
        parts.append(f"{i}. [{q.kind}] {q.question_hu} ({q.question_en})\n   Answer: {answer}")
    parts.append("WRITING TASKS:")
    for i, w in enumerate(exercise.writing_prompts, 1):
        text = submission.writing.get(f"w{i}", "").strip() or "(no text)"
        parts.append(
            f"{i}. [{w.kind}, {w.min_words}-{w.max_words} words] {w.prompt_hu} "
            f"({w.prompt_en})\n   Learner's text ({len(text.split())} words):\n{text}"
        )
    return "\n\n".join(parts)


def grade(llm: LLMProvider, exercise: WritingExercise, submission: Submission) -> GradedFeedback:
    feedback = llm.generate_structured(
        GRADING_SYSTEM, grading_prompt(exercise, submission), Feedback
    )
    return GradedFeedback(
        **feedback.model_dump(), week_id=exercise.week_id, graded_at=datetime.now(UTC)
    )


# ---------- encrypted storage ----------


class WritingStore:
    def __init__(self, data_dir: Path, password: str):
        self.root = data_dir / "writing"
        self.password = password

    def exercise_path(self, week_id: str) -> Path:
        return self.root / f"{week_id}.enc.json"

    def submission_path(self, week_id: str) -> Path:
        return self.root / "submissions" / f"{week_id}.enc.json"

    def feedback_path(self, week_id: str) -> Path:
        return self.root / "feedback" / f"{week_id}.enc.json"

    def _write(self, path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = crypto.encrypt_json(model.model_dump(mode="json"), self.password)
        path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")

    def _read(self, path: Path) -> dict:
        return crypto.decrypt_json(json.loads(path.read_text(encoding="utf-8")), self.password)

    def save_exercise(self, exercise: WritingExercise) -> None:
        self._write(self.exercise_path(exercise.week_id), exercise)

    def load_exercise(self, week_id: str) -> WritingExercise:
        return WritingExercise.model_validate(self._read(self.exercise_path(week_id)))

    def load_submission(self, week_id: str) -> Submission:
        return Submission.model_validate(self._read(self.submission_path(week_id)))

    def save_feedback(self, feedback: GradedFeedback) -> None:
        self._write(self.feedback_path(feedback.week_id), feedback)

    def load_feedback(self, week_id: str) -> GradedFeedback:
        return GradedFeedback.model_validate(self._read(self.feedback_path(week_id)))

    def recent_themes(self, limit: int = 8) -> list[str]:
        themes = []
        for path in sorted(self.root.glob("*.enc.json"))[-limit:]:
            try:
                themes.append(WritingExercise.model_validate(self._read(path)).theme)
            except Exception:  # unreadable or old format: themes are only a hint
                continue
        return themes

    def ungraded_weeks(self) -> list[str]:
        subs = self.root / "submissions"
        if not subs.exists():
            return []
        weeks = [p.name.removesuffix(".enc.json") for p in sorted(subs.glob("*.enc.json"))]
        return [w for w in weeks if not self.feedback_path(w).exists()]


# ---------- email ----------


def feedback_email_html(exercise: WritingExercise, sub: Submission, fb: GradedFeedback) -> str:
    def p(text: str) -> str:
        return escape(text).replace("\n", "<br>")

    rows = []
    for a in fb.answers:
        in_range = 0 < a.question <= len(exercise.questions)
        q = exercise.questions[a.question - 1] if in_range else None
        answer = sub.answers.get(f"q{a.question}", "") or "(no answer)"
        rows.append(
            f"<h4>Q{a.question}. {escape(q.question_hu) if q else ''} "
            f"<span style='color:#777;font-weight:normal'>— {escape(a.verdict)}, "
            f"{a.score}/10</span></h4>"
            f"<p><b>Your answer:</b> {p(answer)}</p><p>{p(a.feedback)}</p>"
            f"<p style='color:#555'><b>Model answer:</b> {p(a.model_answer_hu)}</p>"
        )
    for w in fb.writing:
        corrections = "".join(
            f"<tr><td style='padding:4px 8px;color:#b33'>{escape(c.original)}</td>"
            f"<td style='padding:4px 8px;color:#272'>{escape(c.corrected)}</td>"
            f"<td style='padding:4px 8px'>{escape(c.explanation)}</td></tr>"
            for c in w.corrections
        )
        strengths = "".join(f"<li>{escape(s)}</li>" for s in w.strengths)
        rows.append(
            f"<h4>Writing task {w.prompt} — {w.score}/10 ({escape(w.level_estimate)})</h4>"
            f"<p>{p(w.comments)}</p><ul>{strengths}</ul>"
            f"<table style='border-collapse:collapse;font-size:14px'>"
            f"<tr><th align=left>You wrote</th><th align=left>Better</th>"
            f"<th align=left>Why</th></tr>{corrections}</table>"
            f"<p><b>Improved version:</b><br>{p(w.improved_version_hu)}</p>"
        )
    steps = "".join(f"<li>{escape(s)}</li>" for s in fb.next_steps)
    return f"""\
<div style="font-family:system-ui,sans-serif;max-width:720px;line-height:1.5">
  <h2>Reading &amp; writing feedback — {escape(fb.week_id)}</h2>
  <p><b>{escape(exercise.title_hu)}</b> ({escape(exercise.title_en)})</p>
  <p>Reading: <b>{fb.reading_score_pct}%</b> · Writing: <b>{fb.writing_score_pct}%</b> ·
     Estimated level: <b>{escape(fb.level_estimate)}</b></p>
  <p>{p(fb.summary)}</p>
  {''.join(rows)}
  <h3>Next steps</h3><ul>{steps}</ul>
</div>"""
