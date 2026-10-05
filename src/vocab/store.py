"""Read/write the encrypted JSON files under data/.

Every file is stored as `<name>.enc.json` (see vocab.crypto). Plaintext `<name>.json` files
from before encryption are still read, and are deleted the first time the file is saved.
"""

import json
from pathlib import Path

from pydantic import BaseModel

from vocab import crypto
from vocab.models import Bank, ListIndex, TestResult, WordList


class Store:
    def __init__(self, data_dir: Path, password: str):
        self.root = data_dir
        self.password = password
        self.lists_dir = data_dir / "lists"
        self.results_dir = data_dir / "results"
        self._salt: bytes | None = None

    # ---------- encrypted file helpers ----------

    @staticmethod
    def _enc(stem: Path) -> Path:
        return stem.with_name(stem.name + ".enc.json")

    @staticmethod
    def _legacy(stem: Path) -> Path:
        return stem.with_name(stem.name + ".json")

    @property
    def salt(self) -> bytes:
        if self._salt is None:
            self._salt = crypto.load_or_create_salt(self.root)
        return self._salt

    def _read(self, stem: Path) -> dict | None:
        enc, legacy = self._enc(stem), self._legacy(stem)
        if enc.exists():
            return crypto.decrypt_json(json.loads(enc.read_text(encoding="utf-8")), self.password)
        if legacy.exists():
            return json.loads(legacy.read_text(encoding="utf-8"))
        return None

    def _write(self, stem: Path, model: BaseModel) -> None:
        stem.parent.mkdir(parents=True, exist_ok=True)
        data = model.model_dump(mode="json", exclude_none=True)
        envelope = crypto.encrypt_json(data, self.password, self.salt)
        self._enc(stem).write_text(json.dumps(envelope) + "\n", encoding="utf-8")
        self._legacy(stem).unlink(missing_ok=True)

    def _exists(self, stem: Path) -> bool:
        return self._enc(stem).exists() or self._legacy(stem).exists()

    # ---------- data ----------

    def _list_stem(self, list_id: str) -> Path:
        return self.lists_dir / list_id

    def load_bank(self) -> Bank:
        data = self._read(self.root / "bank")
        return Bank.model_validate(data) if data is not None else Bank()

    def save_bank(self, bank: Bank) -> None:
        self._write(self.root / "bank", bank)

    def load_index(self) -> ListIndex:
        data = self._read(self.lists_dir / "index")
        return ListIndex.model_validate(data) if data is not None else ListIndex()

    def save_index(self, index: ListIndex) -> None:
        index.lists.sort(key=lambda e: e.id)
        self._write(self.lists_dir / "index", index)

    def has_list(self, list_id: str) -> bool:
        return self._exists(self._list_stem(list_id))

    def load_list(self, list_id: str) -> WordList:
        data = self._read(self._list_stem(list_id))
        if data is None:
            raise FileNotFoundError(f"No word list {list_id}")
        return WordList.model_validate(data)

    def save_list(self, word_list: WordList) -> None:
        self._write(self._list_stem(word_list.id), word_list)

    def latest_list_id(self) -> str | None:
        index = self.load_index()
        return index.lists[-1].id if index.lists else None

    def result_ids(self) -> list[str]:
        if not self.results_dir.exists():
            return []
        names = {p.name.split(".")[0] for p in self.results_dir.glob("*-test*.json")}
        return sorted(names)

    def load_results(self) -> list[TestResult]:
        return [
            TestResult.model_validate(self._read(self.results_dir / name))
            for name in self.result_ids()
        ]

    def encrypt_results(self) -> int:
        """Re-save plaintext results (from before encryption) encrypted. Returns how many."""
        count = 0
        for name in self.result_ids():
            stem = self.results_dir / name
            if self._legacy(stem).exists():
                self._write(stem, TestResult.model_validate(self._read(stem)))
                count += 1
        return count
