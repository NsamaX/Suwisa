import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from suwisa.features.receipts.classification import BANK_LABELS, classification_label, classify
from suwisa.features.receipts.models import ReceiptError, ReceiptScan
from suwisa.features.receipts.parser import AMOUNT_WARNING, DATE_WARNING, parse_money
from suwisa.features.receipts.presentation import receipt_embed
from suwisa.infrastructure.storage import ReceiptRepository

log = logging.getLogger(__name__)


class ReviewView(discord.ui.View):
    def __init__(
        self, scan: ReceiptScan, repository: ReceiptRepository, guild_id: int, user_id: int
    ):
        super().__init__(timeout=600)
        self.scan = scan
        self.repository = repository
        self.guild_id = guild_id
        self.user_id = user_id
        self.message: discord.Message | discord.InteractionMessage | None = None
        self.closed = False
        self.lock = asyncio.Lock()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("รายการนี้ให้ผู้ส่งรูปตรวจสอบเท่านั้น", ephemeral=True)
            return False
        if self.closed or self.is_finished():
            await interaction.response.send_message("รายการนี้ปิดแล้ว กรุณาส่งรูปใหม่", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="ยืนยันผลอ่าน", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        async with self.lock:
            if self.closed:
                return
            try:
                receipt_id, created = await asyncio.to_thread(
                    self.repository.save,
                    self.scan,
                    self.guild_id,
                    self.user_id,
                )
            except ReceiptError as exc:
                await interaction.followup.send(str(exc), ephemeral=True)
                return
            except Exception as exc:
                log.error("Receipt save failed (%s)", type(exc).__name__)
                await interaction.followup.send("เก็บข้อมูลไม่สำเร็จ กรุณาลองอีกครั้ง", ephemeral=True)
                return
            self.closed = True
            self.stop()
            text = (
                f"บันทึกรายการแล้ว เลขที่ {receipt_id} • {classification_label(self.scan.receipt)}"
                if created
                else f"รายการเดิมเลขที่ {receipt_id} • {classification_label(self.scan.receipt)} • ไม่เพิ่มรายการซ้ำ"
            )
            await interaction.edit_original_response(content=text, view=None)

    @discord.ui.select(
        placeholder="แก้ธนาคารผู้ออกสลิป (ใช้กำหนดรายรับ/รายจ่าย)",
        options=[
            discord.SelectOption(label=label, value=bank) for bank, label in BANK_LABELS.items()
        ],
        row=1,
    )
    async def bank(self, interaction: discord.Interaction, select: discord.ui.Select):
        async with self.lock:
            if self.closed:
                await interaction.response.send_message("รายการนี้ปิดแล้ว", ephemeral=True)
                return
            classify(self.scan.receipt, select.values[0])
            await interaction.response.edit_message(
                embed=receipt_embed(self.scan.receipt), view=self
            )

    @discord.ui.button(label="แก้ไข", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EditReceiptModal(self))

    @discord.ui.button(label="ทิ้งผลอ่าน", style=discord.ButtonStyle.secondary)
    async def discard(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with self.lock:
            if self.closed:
                await interaction.response.send_message("รายการนี้ปิดแล้ว", ephemeral=True)
                return
            self.closed = True
            self.stop()
            await interaction.response.edit_message(
                content="ทิ้งผลอ่านแล้ว ไม่ได้บันทึกข้อมูล", embed=None, view=None
            )

    async def on_timeout(self):
        async with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.message:
                try:
                    await self.message.edit(
                        content="หมดเวลาตรวจสอบ ยังไม่ได้บันทึก กรุณาส่งรูปใหม่", view=None
                    )
                except discord.HTTPException:
                    pass

    async def on_error(self, interaction, error, item):
        log.error("Receipt review failed (%s)", type(error).__name__)
        if interaction.response.is_done():
            await interaction.followup.send("ทำรายการไม่สำเร็จ กรุณาส่งรูปใหม่", ephemeral=True)
        else:
            await interaction.response.send_message("ทำรายการไม่สำเร็จ กรุณาส่งรูปใหม่", ephemeral=True)


class EditReceiptModal(discord.ui.Modal, title="แก้ไขผลอ่านจากภาพ"):
    def __init__(self, view: ReviewView):
        super().__init__(timeout=300)
        self.review = view
        receipt = view.scan.receipt
        self.amount = discord.ui.TextInput(
            label="ยอดเงิน (THB)", default=str(receipt.amount or ""), max_length=20
        )
        self.recipient = discord.ui.TextInput(
            label="ผู้รับ / ร้านค้า", default=receipt.recipient or "", required=False, max_length=300
        )
        self.date = discord.ui.TextInput(
            label="วันเวลา ค.ศ. เช่น 2026-09-10 20:25",
            default=receipt.occurred_at.strftime("%Y-%m-%d %H:%M") if receipt.occurred_at else "",
            required=False,
            max_length=16,
        )
        self.fee = discord.ui.TextInput(
            label="ค่าธรรมเนียม (THB)",
            default=str(receipt.fee) if receipt.fee is not None else "",
            required=False,
            max_length=20,
        )
        for item in (self.amount, self.recipient, self.date, self.fee):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.review.interaction_check(interaction):
            return
        amount = parse_money(self.amount.value)
        fee = parse_money(self.fee.value) if self.fee.value.strip() else None
        if amount is None or amount <= 0 or (self.fee.value.strip() and fee is None):
            await interaction.response.send_message(
                "ยอดต้องมากกว่า 0 ค่าธรรมเนียมต้องไม่ติดลบ และมีทศนิยมไม่เกิน 2 ตำแหน่ง", ephemeral=True
            )
            return
        try:
            date = (
                datetime.strptime(self.date.value.strip(), "%Y-%m-%d %H:%M").replace(
                    tzinfo=ZoneInfo("Asia/Bangkok")
                )
                if self.date.value.strip()
                else None
            )
        except ValueError:
            await interaction.response.send_message(
                "กรอกวันเวลาเป็น ค.ศ. รูปแบบ YYYY-MM-DD HH:MM", ephemeral=True
            )
            return
        async with self.review.lock:
            if self.review.closed:
                await interaction.response.send_message("รายการนี้ปิดแล้ว", ephemeral=True)
                return
            receipt = self.review.scan.receipt
            receipt.amount, receipt.fee, receipt.currency = amount, fee, "THB"
            receipt.recipient, receipt.occurred_at = self.recipient.value.strip() or None, date
            receipt.warnings = [
                w for w in receipt.warnings if w not in {AMOUNT_WARNING, DATE_WARNING}
            ]
            if date is None:
                receipt.warnings.append(DATE_WARNING)
            await interaction.response.edit_message(embed=receipt_embed(receipt), view=self.review)
