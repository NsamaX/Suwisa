"""The owner's bookkeeping convention, not a universal bank accounting rule."""

from suwisa.features.receipts.models import Receipt

BANK_TYPES = {"BKK": "expense", "KBANK": "income", "KTB": "income"}
BANK_LABELS = {"BKK": "BKK · กรุงเทพ", "KBANK": "KBank · กสิกรไทย", "KTB": "KTB · กรุงไทย"}
TYPE_LABELS = {"expense": "รายจ่าย", "income": "รายรับ"}
UNKNOWN_BANK_WARNING = "ยังระบุธนาคารผู้ออกสลิปไม่ได้ เลือกธนาคารเพื่อจัดประเภทรายการ"


def classify(receipt: Receipt, bank: str | None) -> None:
    if bank is not None and bank not in BANK_TYPES:
        raise ValueError("Unsupported issuing bank")
    receipt.issuer_bank = bank
    receipt.transaction_type = BANK_TYPES.get(bank)
    receipt.warnings = [w for w in receipt.warnings if w != UNKNOWN_BANK_WARNING]
    if bank is None:
        receipt.warnings.append(UNKNOWN_BANK_WARNING)


def classification_label(receipt: Receipt) -> str:
    if receipt.issuer_bank in BANK_TYPES:
        return (
            f"{TYPE_LABELS[BANK_TYPES[receipt.issuer_bank]]} ({BANK_LABELS[receipt.issuer_bank]})"
        )
    return "ยังไม่จัดประเภท"
