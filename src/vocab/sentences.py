"""Future extension: sentence practice built from words in the bank.

Planned design (not implemented yet):
- `generate_sentences(llm, bank_words, n)` asks the LLM for short EN/HU sentence pairs, each
  tagged with the bank `word_ids` it uses.
- Results become `Card(type="sentence", word_ids=[...])` appended to a list's `cards`; the site
  already renders cards generically, and `bank.apply_result` updates every linked word.
- A `--with-sentences` flag on `vocab generate` / `vocab weekly` will switch it on, most likely
  for the end-of-week test phase.
"""

from vocab.llm.base import LLMProvider
from vocab.models import BankEntry, Card


def generate_sentences(llm: LLMProvider, bank_words: list[BankEntry], n: int) -> list[Card]:
    raise NotImplementedError("Sentence generation is a planned extension.")
