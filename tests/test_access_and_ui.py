from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from suwisa.config import Settings, id_set
from suwisa.features.receipts.cog import ReceiptCog
from suwisa.features.receipts.models import Receipt, ReceiptError, ReceiptScan
from suwisa.features.receipts.presentation import receipt_embed
from suwisa.features.receipts.views import ReviewView
from suwisa.infrastructure.storage import ReceiptRepository


def settings():
    return Settings("test-token", 1, frozenset({2}), frozenset({3}))


def test_access_is_closed_for_other_users_channels_guilds_and_dms():
    config = settings()
    assert config.permits(2, 1, 3)
    for user, guild, channel in [(9, 1, 3), (2, 9, 3), (2, 1, 9), (2, None, 3)]:
        assert not config.permits(user, guild, channel)
    assert "test-token" not in repr(config)
    with pytest.raises(ValueError):
        id_set("", "users")


async def test_unapproved_message_never_downloads_image():
    bot = SimpleNamespace(settings=settings())
    cog = ReceiptCog(bot)
    attachment = SimpleNamespace(read=AsyncMock())
    message = SimpleNamespace(
        author=SimpleNamespace(id=9, bot=False),
        guild=SimpleNamespace(id=1),
        channel=SimpleNamespace(id=3),
        attachments=[attachment],
    )
    await cog.on_message(message)
    attachment.read.assert_not_awaited()


async def test_one_ocr_per_user_and_slot_released_after_error():
    cog = ReceiptCog(SimpleNamespace())
    with pytest.raises(RuntimeError):
        async with cog.slot(1):
            with pytest.raises(ReceiptError):
                async with cog.slot(1):
                    pass
            raise RuntimeError("synthetic failure")
    assert not cog.busy_users


async def test_review_owner_and_confirm_storage(tmp_path):
    repo = ReceiptRepository(tmp_path / "data.sqlite3")
    scan = ReceiptScan(Receipt(amount=Decimal("88.50"), currency="THB"), "synthetic-hash", 90)
    view = ReviewView(scan, repo, 1, 2)
    other = SimpleNamespace(
        user=SimpleNamespace(id=9), response=SimpleNamespace(send_message=AsyncMock())
    )
    assert not await view.interaction_check(other)
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=2),
        response=SimpleNamespace(defer=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    assert await view.interaction_check(interaction)
    await view.confirm.callback(interaction)
    assert view.closed
    assert repo.save(scan, 1, 2) == (1, False)
    interaction.edit_original_response.assert_awaited_once()


async def test_expired_review_does_not_write(tmp_path):
    repo = Mock(spec=ReceiptRepository)
    view = ReviewView(ReceiptScan(Receipt(), "a", 1), repo, 1, 2)
    view.message = SimpleNamespace(edit=AsyncMock())
    await view.on_timeout()
    assert view.closed
    repo.save.assert_not_called()
    view.stop()


def test_ocr_text_cannot_ping_people_or_exceed_embed_limits():
    embed = receipt_embed(Receipt(recipient="@everyone **hello**" * 200))
    assert "@everyone" not in embed.fields[3].value
    assert len(embed.fields[3].value) <= 1024
    assert len(embed) < 6000


async def test_bank_menu_changes_classification_before_save():
    repo = Mock(spec=ReceiptRepository)
    view = ReviewView(ReceiptScan(Receipt(), "a", 90), repo, 1, 2)
    view.bank._values = ["KBANK"]
    interaction = SimpleNamespace(response=SimpleNamespace(edit_message=AsyncMock()))
    await view.bank.callback(interaction)
    assert view.scan.receipt.issuer_bank == "KBANK"
    assert view.scan.receipt.transaction_type == "income"
    repo.save.assert_not_called()
    interaction.response.edit_message.assert_awaited_once()
    view.stop()
