"""Parse notes pasted from a tutoring-lesson chat into vocabulary, sentences and topics.

The paste is messy: chat metadata ("img", the tutor's name, timestamps) is mixed in, and the
GitHub "Run workflow" form strips line breaks, gluing everything together. `clean_chat`
removes the metadata (and turns it back into line breaks); the LLM does the rest.
"""

import re

from pydantic import BaseModel, Field

from vocab.llm.base import LLMProvider
from vocab.models import GeneratedWord

_UPPER = "A-ZÁÉÍÓÖŐÚÜŰ"
_LOWER = "a-záéíóöőúüű"
# "img Timea H. 18:34" — optional image marker, a "Firstname X." sender, a timestamp.
_SENDER_STAMP = re.compile(
    rf"(?:img)?\s*[{_UPPER}][{_LOWER}]+\s+[{_UPPER}]\.\s*\d{{1,2}}:\d{{2}}"
)
_LONE_TIME = re.compile(r"^\s*\d{1,2}:\d{2}\s*$", re.MULTILINE)
_LONE_IMG = re.compile(r"^\s*img\s*$|img\s*$", re.MULTILINE)


def clean_chat(text: str) -> str:
    """Strip chat metadata and blank lines, keeping one note per line."""
    text = _SENDER_STAMP.sub("\n", text)
    text = _LONE_TIME.sub("", text)
    text = _LONE_IMG.sub("", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


class LessonSentence(BaseModel):
    hu: str = Field(description="The sentence in correct, natural Hungarian")
    en: str = Field(description="English translation")


class LessonNotes(BaseModel):
    topics: list[str] = Field(description="3-8 short English topics the lesson covered")
    vocabulary: list[GeneratedWord] = Field(
        description="Each distinct word or short phrase worth learning from the notes"
    )
    sentences: list[LessonSentence] = Field(
        description="Full sentences from the notes, corrected where needed"
    )
    grammar_points: list[str] = Field(
        description="Grammar covered, in English, e.g. 'multiplicative suffix -szor/-szer/-ször'"
    )


LESSON_SYSTEM = """\
You help a native English speaker learning Hungarian turn their tutor's lesson notes into \
study material. The notes were typed into a chat during the lesson: single words, phrases, \
translations ("rendelet- regulation"), alternatives ("marhahús/tehénhús"), and sentences \
the learner tried to say that the tutor wrote out correctly. Some chat debris may remain \
(e.g. "img", names, times); ignore it. The notes may have lost their line breaks, so use \
Hungarian grammar to work out where one note ends and the next begins.

- vocabulary: every distinct word or useful short phrase, in base form — nouns in \
nominative singular, adjectives in base form, VERBS IN THE INFINITIVE (e.g. "jöttek" -> \
"jönni", "lelőttek" -> "lelőni", "paintballozni" stays). Use the tutor's translation when \
given. For the example sentence, prefer a sentence from the notes that uses the word. \
Include words that only appear inside sentences if they are useful for the learner. Treat \
suffixes (like -szor/-szer/-ször) as grammar points, not vocabulary.
- sentences: each full sentence or clause from the notes, corrected if it contains an \
error, with a natural English translation.
- topics: what the lesson talked about, as short English topics.
- grammar_points: grammar the notes show, explained in a few English words.
Use correct Hungarian spelling with all accents."""


def parse_lesson(llm: LLMProvider, text: str) -> LessonNotes:
    notes = clean_chat(text)
    return llm.generate_structured(
        LESSON_SYSTEM, f"Lesson notes:\n\n{notes}", LessonNotes
    )
