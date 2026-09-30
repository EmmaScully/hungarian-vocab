"""Read/write the JSON files under data/."""

import json
from pathlib import Path

from pydantic import BaseModel

from vocab.models import Bank, ListIndex, TestResult, WordList


class Store:
    def __init__(self, data_dir: Path):
        self.root = data_dir
        self.bank_path = data_dir / "bank.json"
        self.lists_dir = data_dir / "lists"
        self.results_dir = data_dir / "results"
        self.index_path = self.lists_dir / "index.json"

    def _write(self, path: Path, model: BaseModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = model.model_dump(mode="json", exclude_none=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def load_bank(self) -> Bank:
        if not self.bank_path.exists():
            return Bank()
        return Bank.model_validate_json(self.bank_path.read_text(encoding="utf-8"))

    def save_bank(self, bank: Bank) -> None:
        self._write(self.bank_path, bank)

    def load_index(self) -> ListIndex:
        if not self.index_path.exists():
            return ListIndex()
        return ListIndex.model_validate_json(self.index_path.read_text(encoding="utf-8"))

    def save_index(self, index: ListIndex) -> None:
        index.lists.sort(key=lambda e: e.id)
        self._write(self.index_path, index)

    def list_path(self, list_id: str) -> Path:
        return self.lists_dir / f"{list_id}.json"

    def load_list(self, list_id: str) -> WordList:
        return WordList.model_validate_json(self.list_path(list_id).read_text(encoding="utf-8"))

    def save_list(self, word_list: WordList) -> None:
        self._write(self.list_path(word_list.id), word_list)

    def latest_list_id(self) -> str | None:
        index = self.load_index()
        return index.lists[-1].id if index.lists else None

    def load_results(self) -> list[TestResult]:
        if not self.results_dir.exists():
            return []
        return [
            TestResult.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(self.results_dir.glob("*-test.json"))
        ]
