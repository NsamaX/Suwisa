import discord

from suwisa.features.receipts.classification import classification_label
from suwisa.features.receipts.models import Receipt


def safe_text(value: str | None) -> str:
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value or "อ่านไม่ชัด"))[:1000]


def receipt_embed(receipt: Receipt) -> discord.Embed:
    embed = discord.Embed(title="ผลอ่านใบเสร็จ / สลิป", color=0x7966D8)
    embed.description = "ตรวจยอด วันเวลา และผู้รับก่อนกดยืนยัน สามารถแก้ไขข้อมูลที่อ่านคลาดเคลื่อนได้"
    embed.add_field(
        name="ยอดเงิน",
        value=f"{receipt.amount:,.2f} {receipt.currency or '(ไม่ทราบสกุลเงิน)'}"
        if receipt.amount is not None
        else "อ่านไม่ชัด",
    )
    embed.add_field(
        name="ค่าธรรมเนียม", value=f"{receipt.fee:,.2f}" if receipt.fee is not None else "ไม่พบ"
    )
    embed.add_field(
        name="วันเวลา (กรุงเทพฯ)",
        value=receipt.occurred_at.strftime("%d/%m/%Y %H:%M") if receipt.occurred_at else "อ่านไม่ชัด",
        inline=False,
    )
    embed.add_field(name="ผู้รับ / ร้านค้า", value=safe_text(receipt.recipient), inline=False)
    embed.add_field(name="ประเภทรายการ", value=classification_label(receipt), inline=False)
    if receipt.warnings:
        embed.add_field(
            name="โปรดตรวจสอบ",
            value="\n".join(f"• {safe_text(w)}" for w in receipt.warnings)[:1024],
            inline=False,
        )
    embed.set_footer(text="จัดประเภทตามธนาคารผู้ออกสลิป • บันทึกเมื่อยืนยัน • ไม่ใช่การตรวจสลิปแท้")
    return embed
