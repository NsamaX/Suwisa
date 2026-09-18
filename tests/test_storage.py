import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal

import pytest

from suwisa.features.receipts.models import Receipt, ReceiptError, ReceiptScan
from suwisa.infrastructure.storage import ReceiptRepository


def scan(digest="a", reference=None, amount="88.50"):
    return ReceiptScan(
        Receipt(amount=Decimal(amount), currency="THB", reference=reference), digest, 90
    )


def test_duplicate_hash_and_reference_are_scoped_to_owner(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    first = repo.save(scan(reference="example-reference"), 1, 2)
    assert first == (1, True)
    assert repo.save(scan(), 1, 2) == (1, False)
    assert repo.save(scan("new-image", "example-reference"), 1, 2) == (1, False)
    assert repo.save(scan(reference="example-reference"), 1, 3)[1] is True


def test_concurrent_confirmations_create_one_record(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: repo.save(scan(), 1, 2), range(8)))
    assert sum(created for _, created in results) == 1


def test_backup_can_be_restored_with_exact_decimal_values(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    repo.save(scan(), 1, 2)
    target = tmp_path / "backup.sqlite3"
    repo.backup(target)
    with closing(sqlite3.connect(target)) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        payload = json.loads(connection.execute("SELECT payload FROM receipts").fetchone()[0])
    assert payload["amount"] == "88.50"
    assert "raw_text" not in payload


def test_unread_or_zero_total_cannot_be_confirmed(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    with pytest.raises(ReceiptError):
        repo.save(scan(amount="0"), 1, 2)
    with pytest.raises(ValueError):
        repo.backup(repo.path)


def test_reconfirm_legacy_receipt_adds_classification_without_duplicate(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    original = scan()
    repo.save(original, 1, 2)
    from suwisa.features.receipts.classification import classify

    classify(original.receipt, "BKK")
    assert repo.save(original, 1, 2) == (1, False)
    with closing(repo.connect()) as db:
        assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 1
        payload = json.loads(db.execute("SELECT payload FROM receipts").fetchone()[0])
    assert payload["transaction_type"] == "expense"
    assert payload["issuer_bank"] == "BKK"
    assert payload["amount"] == "88.50"


def test_classification_cannot_overwrite_a_different_reviewed_amount(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    repo.save(scan(), 1, 2)
    changed = scan(amount="99.99")
    from suwisa.features.receipts.classification import classify

    classify(changed.receipt, "KBANK")
    with pytest.raises(ReceiptError):
        repo.save(changed, 1, 2)
    with closing(repo.connect()) as db:
        payload = json.loads(db.execute("SELECT payload FROM receipts").fetchone()[0])
    assert payload["amount"] == "88.50"
    assert payload["issuer_bank"] is None


def test_bank_type_mismatch_is_rejected(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    item = scan()
    item.receipt.issuer_bank = "BKK"
    item.receipt.transaction_type = "income"
    with pytest.raises(ReceiptError):
        repo.save(item, 1, 2)
