from decimal import Decimal

import pytest

from suwisa.features.receipts.models import OcrDocument
from suwisa.features.receipts.parser import parse_date, parse_money, parse_receipt


def doc(text, date_text=""):
    return OcrDocument(text, 90, date_text)


def test_synthetic_bank_slip_keeps_amount_fee_and_reference_separate():
    receipt = parse_receipt(
        doc("""
Bangkok Bank
รายการสำเร็จ
7 ก.ย. 69, 09:15
จำนวนเงิน
1,234.56 THB
จาก นาย ทดสอบ
999-9-xxx999
ไปที่ ร้านตัวอย่าง
หมายเลขโทรศัพท์
0000000000
ค่าธรรมเนียม 5.00 THB
เลขที่อ้างอิง
99999999999999999999999
""")
    )
    assert receipt.amount == Decimal("1234.56")
    assert receipt.fee == Decimal("5.00")
    assert receipt.recipient == "ร้านตัวอย่าง"
    assert receipt.occurred_at.isoformat() == "2026-09-07T09:15:00+07:00"
    assert receipt.reference == "99999999999999999999999"
    assert "0000000000" not in str(receipt.to_dict())


@pytest.mark.parametrize(
    "month,number",
    [
        ("ม.ค.", 1),
        ("ก.พ.", 2),
        ("มี.ค.", 3),
        ("เม.ย.", 4),
        ("พ.ค.", 5),
        ("มิ.ย.", 6),
        ("ก.ค.", 7),
        ("ส.ค.", 8),
        ("ก.ย.", 9),
        ("ต.ค.", 10),
        ("พ.ย.", 11),
        ("ธ.ค.", 12),
    ],
)
def test_thai_months_and_buddhist_years(month, number):
    value = parse_date(f"07 {month} 2569, 09:15")
    assert (value.year, value.month, value.day) == (2026, number, 7)


def test_date_retry_uses_thai_crop_and_does_not_infer_from_reference():
    receipt = parse_receipt(
        doc("Bangkok Bank\n7 n.g.69, 09:15\nจำนวนเงิน\n88.50 THB", "7 ก.ุย.69, 09:15")
    )
    assert receipt.occurred_at.month == 9
    assert parse_date("2026090709150000000000000") is None
    assert parse_date("31 ก.พ.69, 09:15") is None


def test_labeled_total_not_subtotal_change_or_phone():
    receipt = parse_receipt(
        doc(
            "EXAMPLE SHOP\nSUBTOTAL 80.00\nVAT 8.50\nTOTAL 88.50 THB\nCASH 100.00\nCHANGE 11.50\n0000000000"
        )
    )
    assert receipt.amount == Decimal("88.50")


def test_unlabeled_or_ambiguous_money_is_never_guessed():
    assert parse_receipt(doc("Call 0000000000\nPrice 100.00\nCash 200.00")).amount is None
    receipt = parse_receipt(doc("ยอดรวม 50.00\nยอดรวม 60.00"))
    assert receipt.amount is None
    assert any("หลายค่า" in warning for warning in receipt.warnings)


def test_bkk_wallet_is_expense_per_owner_policy():
    receipt = parse_receipt(
        doc("Bangkok Bank\nจำนวนเงิน\n88.50 THB\nไปที่ ng มันนี่\nService Code:TMNTOPUP")
    )
    assert receipt.recipient == "ทรูมันนี่ วอลเล็ท"
    assert receipt.issuer_bank == "BKK"
    assert receipt.transaction_type == "expense"
    assert not any("ย้ายเงิน" in warning for warning in receipt.warnings)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "12.345", "1000000000", "junk"])
def test_invalid_money_is_rejected(value):
    assert parse_money(value) is None


def test_thai_digits_and_unknown_currency():
    receipt = parse_receipt(doc("ยอดรวม ๘๘.๕๐ บาท\n07/09/2026 09:15"))
    assert receipt.amount == Decimal("88.50")
    assert receipt.currency == "THB"
    assert parse_receipt(doc("TOTAL 88.50 USD")).currency is None


def test_reference_label_with_dropped_tone_marks():
    receipt = parse_receipt(doc("Bangkok Bank\nเลขทีอ้างอิง\n99999999999999999999999"))
    assert receipt.reference == "99999999999999999999999"


def test_bank_brand_does_not_override_explicit_foreign_currency():
    receipt = parse_receipt(doc("Bangkok Bank\nจำนวนเงิน\n88.50 USD"))
    assert receipt.currency is None


def test_kbank_issuer_wins_over_bangkok_recipient():
    receipt = parse_receipt(
        doc("""
โอนเงินสำเร็จ K+
7 ก.ย. 69 09:15 น.
นาย ผู้ส่งทดสอบ
ธ.กสิกรไทย
xxx-x-x1111-x
นาย ผู้รับทดสอบ
ธ.กรุงเทพ
xxx-x-x2222-x
เลขที่รายการ:
0123456789TEST1234
จำนวน:
88.50 บาท
ค่าธรรมเนียม:
0.00 บาท
""")
    )
    assert receipt.issuer_bank == "KBANK"
    assert receipt.transaction_type == "income"
    assert receipt.amount == Decimal("88.50")
    assert receipt.recipient == "นาย ผู้รับทดสอบ"
    assert receipt.reference == "0123456789TEST1234"
    assert receipt.occurred_at.isoformat() == "2026-09-07T09:15:00+07:00"


def test_ktb_layout_hyphen_date_and_alphanumeric_reference():
    receipt = parse_receipt(
        doc("""
Krungthai กรุงไทย
โอนเงินสำเร็จ
รหัสอ้างอิง Ac0123456789abcd
จาก
ผู้ส่งทดสอบ ห***
กรุงไทย
XXX-X-XX111-1
ไปยัง
นาย ผู้รับทดสอบ
กรุงเทพ
XXX-X-XX222-2
จำนวนเงิน 1,234.56 บาท
ค่าธรรมเนียม 0.00 บาท
วันที่ทำรายการ 7 ก.ย. 2569 - 09:15
""")
    )
    assert receipt.issuer_bank == "KTB"
    assert receipt.transaction_type == "income"
    assert receipt.amount == Decimal("1234.56")
    assert receipt.recipient == "นาย ผู้รับทดสอบ"
    assert receipt.reference == "Ac0123456789abcd"
    assert receipt.occurred_at.isoformat() == "2026-09-07T09:15:00+07:00"


def test_recipient_bank_alone_does_not_classify_a_slip():
    receipt = parse_receipt(
        doc("โอนเงินสำเร็จ\nนาย ทดสอบ\nxxx-x-x1111-x\nธนาคารกรุงเทพ\nจำนวนเงิน 88.50 บาท")
    )
    assert receipt.issuer_bank is None
    assert receipt.transaction_type is None


def test_kbank_sender_layout_fallback_when_logo_missing():
    receipt = parse_receipt(
        doc(
            "โอนเงินสำเร็จ\nนาย ทดสอบ\nธ.กสิกรไทย\nxxx-x-x1111-x\nนาย ตัวอย่าง\nธ.กรุงเทพ\nxxx-x-x2222-x\nจำนวน: 88.50 บาท"
        )
    )
    assert receipt.issuer_bank == "KBANK"


def test_bkk_wallet_name_does_not_include_garbled_service_code():
    receipt = parse_receipt(
        doc("Bangkok Bank\nจำนวนเงิน\n88.50 THB\nไปที่ ng มันนี่ วอลเล็ท Service 00ด6:1ไหผาอป")
    )
    assert receipt.recipient == "ทรูมันนี่ วอลเล็ท"
    assert receipt.transaction_type == "expense"
