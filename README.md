# Suwisa

เลขาส่วนตัวบน Discord ออกแบบให้เพิ่มฟีเจอร์ทีละส่วน รันบน home server ผ่าน Docker Compose / Dockge

ฟีเจอร์แรกคือ **อ่านใบเสร็จและสลิปด้วย OCR ภาษาไทยบนเครื่อง** ไม่ต้องใช้ AI API key
รองรับตัวแปลข้อความสลิป BKK, KBank และ KTB ใบเสร็จร้านค้าทั่วไปอ่านยอดรวมที่มีป้ายกำกับได้บางรูปแบบ

## การใช้งาน

- ส่งภาพ JPG, PNG หรือ WebP ครั้งละหนึ่งรูปในห้องที่ตั้งค่า บอทจะตอบผลอ่านในห้องนั้น
- หรือใช้ `/receipt image:<รูป>` เพื่อรับผลแบบเห็นเฉพาะผู้ใช้คำสั่ง
- แสดงยอด สกุลเงิน ค่าธรรมเนียม วันเวลา และผู้รับ พร้อมจุดที่ต้องตรวจสอบ
- กด **แก้ไข** เพื่อแก้ยอด ผู้รับ วันเวลา และค่าธรรมเนียม
- กด **ยืนยันผลอ่าน** เพื่อเก็บข้อมูลลง SQLite หรือ **ทิ้งผลอ่าน** เพื่อยกเลิก
- หากไม่ยืนยันภายใน 10 นาที หรือบอทรีสตาร์ตระหว่างตรวจ จะยังไม่บันทึก ให้ส่งภาพใหม่

การยืนยันบันทึกผลอ่านพร้อมประเภทรายการตามกติกาของเจ้าของบอท:

| ธนาคารผู้ออกสลิป | ประเภท |
|---|---|
| BKK / กรุงเทพ | รายจ่ายทั้งหมด รวมเติมวอลเล็ต |
| KBank / กสิกรไทย | รายรับ |
| KTB / กรุงไทย | รายรับ |

ใช้ธนาคาร **ผู้ออกสลิป** ไม่ใช่ธนาคารผู้รับ หากอ่านไม่ชัดให้เลือกธนาคารในเมนูก่อนยืนยัน
กติกานี้เป็นวิธีบันทึกของเจ้าของบอท ไม่ใช่กฎทั่วไปของธนาคาร
ยอดเงินและค่าธรรมเนียมเก็บแยกกัน ยังไม่มีคำสั่งรวมยอดหรือแยกรายการสินค้า และไม่ตรวจสลิปแท้หรือเงินเข้าจริง
รายการเก่าที่ไม่มีข้อมูลธนาคารจะไม่ถูกเดาย้อนหลัง: ส่งภาพเดิมและยืนยันเพื่อเพิ่มประเภทในรายการเดิมโดยไม่เพิ่มรายการซ้ำ
หากยอดอ่านใหม่ไม่ตรงยอดเดิม บอทจะไม่แก้ข้อมูลที่เคยยืนยันไว้

## ขอบเขตรุ่นแรก

- OCR ทำงานบน CPU รูปไม่ถูกส่งต่อไปบริการ OCR ภายนอก
- รูปต้นฉบับอยู่บน Discord ตามปกติ บอทใช้ไฟล์ชั่วคราวระหว่าง OCR แล้วลบ ไม่เก็บสำเนารูป
- เก็บเฉพาะข้อมูลยืนยัน, hash รูป, reference, Discord guild/user ID และเวลายืนยัน
- ไม่เก็บ OCR ดิบ หมายเลขโทรศัพท์ หรือบัญชีผู้ส่ง และไม่พิมพ์ข้อมูลสลิปลง log
- ยังไม่แยกรายการสินค้า ไม่ตรวจ QR ไม่รองรับ PDF/HEIC หรือภาพเอียงมาก
- ชื่อบุคคล/ร้านค้าอาจคลาดเคลื่อน แม้ยอดถูกต้อง จึงต้องตรวจจากภาพเสมอ
- ชื่อ TrueMoney ปรับมาตรฐานจาก `TMNTOPUP` หรือข้อความชื่อวอลเล็ตที่รู้จักบนสลิป BKK
- ยืนยันเฉพาะ THB ปุ่มแก้ไขระบุ THB ชัดเจน
- กันซ้ำด้วย hash รูปและ reference ที่อ่านได้ หากภาพเปลี่ยนและอ่าน reference ไม่ได้ อาจตรวจซ้ำไม่พบ

## โครงสร้าง

```text
src/suwisa/
  __main__.py             # เปิดบอท
  bot.py                  # Discord และลงทะเบียนฟีเจอร์
  config.py               # token, allowlists, limits
  cli.py                  # อ่านรูปในเครื่อง / backup
  features/receipts/
    cog.py                # /receipt และรับรูปจากแชท
    models.py             # ข้อมูล + interface OCR
    service.py            # ขั้นตอนอ่านและแปลข้อมูล
    parser.py             # แปลข้อความเป็นข้อมูล
    classification.py     # กติกาธนาคาร -> รายรับ/รายจ่าย
    presentation.py       # ข้อความตอบกลับ
    views.py              # ยืนยัน / แก้ไข / ทิ้ง
  infrastructure/
    ocr/tesseract.py       # OCR และอ่านบรรทัดวันที่แยก
    storage.py            # SQLite, กันซ้ำ, schema version, backup
 tests/                   # ข้อมูลสมมติ ไม่มีสลิปจริง
 docs/                    # เพิ่มฟีเจอร์และ deploy
 compose.yaml
 Dockerfile
 .env.example
 .gitignore
```

อ่าน [การเพิ่มฟีเจอร์](docs/architecture.md) และ [การ deploy](docs/deployment.md)

## เริ่มด้วย Docker / Dockge

```bash
git clone https://github.com/NsamaX/suwisa.git
cd suwisa
cp .env.example .env
mkdir -p data backups
```

กรอก `.env`:

```dotenv
DISCORD_TOKEN=<Bot token>
DISCORD_GUILD_ID=<Server ID>
ALLOWED_USER_IDS=<Your user ID>
RECEIPT_CHANNEL_IDS=<Channel ID>
```

เปิด Developer Mode ใน Discord แล้วคลิกขวา Copy ID รายการผู้ใช้/ห้องคั่นด้วย comma ได้
ต้องระบุทั้งสามส่วน บอทไม่เริ่มหาก allowlist ว่าง และไม่รับรูปจาก DM

เปิด **Message Content Intent** ใน Developer Portal เชิญด้วย scopes `bot` + `applications.commands`
สิทธิ์ที่ใช้: View Channels, Send Messages, Embed Links, Read Message History; Attach Files เผื่อส่งออกภายหลัง
ใช้ห้องข้อความปกติ รุ่นนี้ยังไม่ได้กำหนดสิทธิ์ Send Messages in Threads ให้โดยอัตโนมัติ

```bash
docker compose up -d --build
docker compose logs -f --tail=100 suwisa
```

Container รันเป็น UID/GID `1000:1000` โฟลเดอร์ bind mount ต้องเขียนได้ด้วย UID นี้
ไม่มี published ports บอทเชื่อมออกไป Discord ผ่าน Gateway

## พัฒนาและอ่านรูปในเครื่อง

Python 3.12 และ Tesseract 5 พร้อมภาษา `tha` + `eng`:

```bash
# Debian / Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install --no-deps -e .
```

Windows ใช้ `.venv\Scripts\Activate.ps1` ตั้ง `TESSERACT_CMD` / `TESSDATA_DIR` ใน `.env`
โฟลเดอร์ภาษาต้องมี `tha.traineddata` และ `eng.traineddata` จาก [Tesseract tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast)

```bash
# ไม่ต้องใช้ Discord token; JSON อาจมีข้อมูลส่วนบุคคล เก็บผลไว้ใน .temp เท่านั้น
suwisa-receipt .temp/example.jpg
# เปิดบอทหลังกรอก .env
suwisa
```

## ทดสอบ

```bash
ruff check .
ruff format --check .
pytest -q
# รวม OCR จริงบนภาพสมมติ ต้องติดตั้งภาษา
RUN_OCR_TESTS=1 pytest -q
```

PowerShell ใช้ `$env:RUN_OCR_TESTS='1'` ก่อน `pytest`
CI ทดสอบ OCR ด้วยภาพสมมติ พร้อม build image และตรวจภาษาใน container
การทดสอบไม่เชื่อม Discord จริง และไม่ต้องมี secrets ใน GitHub Actions

## อ้างอิง

- [discord.py cogs](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html)
- [Discord Gateway](https://docs.discord.com/developers/events/gateway)
- [Tesseract image quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
- [Docker Compose production](https://docs.docker.com/compose/how-tos/production/)
