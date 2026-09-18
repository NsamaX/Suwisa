from dataclasses import asdict, dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol


class ReceiptError(Exception):
    """A user-readable validation or processing error."""


@dataclass(frozen=True)
class OcrDocument:
    text: str
    confidence: float
    date_text: str = ""


class OcrEngine(Protocol):
    def read(self, image: bytes) -> OcrDocument: ...


@dataclass
class Receipt:
    document_type: str = "unknown"
    issuer_bank: str | None = None
    transaction_type: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    occurred_at: datetime | None = None
    recipient: str | None = None
    fee: Decimal | None = None
    reference: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        for key in ("amount", "fee"):
            result[key] = str(result[key]) if result[key] is not None else None
        result["occurred_at"] = self.occurred_at.isoformat() if self.occurred_at else None
        return result


@dataclass(frozen=True)
class ReceiptScan:
    receipt: Receipt
    image_sha256: str
    confidence: float
