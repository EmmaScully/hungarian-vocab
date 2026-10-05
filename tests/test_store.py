import json
from datetime import UTC, datetime

import pytest
from cryptography.exceptions import InvalidTag

from vocab.models import Bank, Card, ListIndex, ListIndexEntry, TestResult, WordList
from vocab.store import Store

NOW = datetime(2026, 10, 5, tzinfo=UTC)
WL = WordList(id="2026-W41", created=NOW, cards=[
    Card(id="bátor", front_en="brave", back_hu="bátor", word_ids=["bátor"])])


def test_everything_is_written_encrypted(tmp_path):
    store = Store(tmp_path, "pw")
    store.save_list(WL)
    store.save_bank(Bank())
    store.save_index(ListIndex(lists=[ListIndexEntry(id="2026-W41", created=NOW, n_cards=1)]))

    files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json"))
    assert files == ["bank.enc.json", "crypto.json", "lists/2026-W41.enc.json",
                     "lists/index.enc.json"]
    assert all("bátor" not in p.read_text() for p in tmp_path.rglob("*.json"))
    # One shared salt, so the browser only derives the key once.
    salts = {json.loads(p.read_text())["salt"] for p in tmp_path.rglob("*.enc.json")}
    assert len(salts) == 1

    assert store.load_list("2026-W41") == WL and store.has_list("2026-W41")
    with pytest.raises(InvalidTag):
        Store(tmp_path, "wrong").load_list("2026-W41")


def test_legacy_plaintext_is_read_then_replaced(tmp_path):
    (tmp_path / "lists").mkdir()
    (tmp_path / "lists" / "2026-W41.json").write_text(WL.model_dump_json())
    (tmp_path / "results").mkdir()
    result = TestResult(list_id="2026-W41", completed_at=NOW, ratings={"bátor": "fail"})
    (tmp_path / "results" / "2026-W41-test.json").write_text(result.model_dump_json())

    store = Store(tmp_path, "pw")
    assert store.has_list("2026-W41") and store.load_list("2026-W41") == WL
    assert store.load_results() == [result]

    store.save_list(store.load_list("2026-W41"))
    assert store.encrypt_results() == 1
    assert not (tmp_path / "lists" / "2026-W41.json").exists()
    assert not (tmp_path / "results" / "2026-W41-test.json").exists()
    assert store.load_results() == [result] and store.load_list("2026-W41") == WL
