# Suwisa

A personal assistant for Discord, designed to grow one feature at a time and run on a home server with Docker Compose / Dockge.

The first feature is **receipt and transfer slip scanning with local Thai OCR**. No AI API key is required.
Text parsers support BKK, KBank, and KTB transfer slips, plus some store receipt layouts with labeled totals.

## Usage

- Send one JPG, PNG, or WebP image at a time in a configured channel. The bot replies with the extracted details in that channel.
- Alternatively, use `/receipt image:<image>` for a response visible only to you.
- Review the amount, currency, fee, date and time, recipient, and any warnings.
- Click **Edit** to correct the amount, recipient, date and time, or fee.
- Click **Confirm reading** to save the details to SQLite, or **Discard reading** to cancel.
- Reviews expire after 10 minutes. If you do not confirm in time, or the bot restarts during review, nothing is saved; submit the image again.

The bot's interface is currently in Thai. Confirmation saves the extracted details with a transaction type based on the owner's rules:

| Slip issuer | Transaction type |
|---|---|
| BKK / Bangkok Bank | Expense, including wallet top-ups |
| KBank / Kasikornbank | Income |
| KTB / Krungthai Bank | Income |

Classification uses the **slip issuer**, not the recipient's bank. If recognition is unclear, select the bank from the menu before confirming.
These are the owner's personal recording rules, not general banking rules.
Amounts and fees are stored separately. There are no total summary commands or itemized purchase records yet, and the bot does not verify slip authenticity or actual receipt of funds.
Older records without bank details are not classified by inference: resubmit the original image and confirm to add a classification to the existing record without creating a duplicate.
If the newly extracted amount differs from the saved amount, the bot leaves the previously confirmed data unchanged.

## Initial scope and limitations

- OCR runs on the CPU. Images are not forwarded to an external OCR service.
- Original images remain on Discord as usual. The bot uses temporary files during OCR, then deletes them without retaining image copies.
- Storage is limited to confirmed details, the image hash, transaction reference, Discord guild/user IDs, and confirmation time.
- Raw OCR text, phone numbers, and sender account numbers are not stored, and slip details are not written to logs.
- Itemized purchases, QR verification, PDF/HEIC files, and heavily tilted images are not supported yet.
- Personal and store names may be inaccurate even when the amount is correct. Always check them against the image.
- TrueMoney names are normalized using `TMNTOPUP` or recognized wallet wording on BKK slips.
- Only THB records can be confirmed. The edit form explicitly identifies the currency as THB.
- Duplicate detection uses the image hash and any extracted transaction reference. It may miss a duplicate if the image changes and the reference cannot be read.

## Project structure

```text
src/suwisa/
  __main__.py             # Bot entry point
  bot.py                  # Discord setup and feature registration
  config.py               # Token, allowlists, and limits
  cli.py                  # Local image scanning and backups
  features/receipts/
    cog.py                # /receipt and images posted in chat
    models.py             # Data models and OCR interface
    service.py            # OCR and parsing workflow
    parser.py             # Text-to-data parsing
    classification.py     # Bank-to-income/expense rules
    presentation.py       # Response formatting
    views.py              # Confirm, edit, and discard controls
  infrastructure/
    ocr/tesseract.py       # OCR and a separate date-line pass
    storage.py            # SQLite, deduplication, schema version, backups
tests/                    # Synthetic data; no real slips
docs/                     # Feature development and deployment guides
compose.yaml
Dockerfile
.env.example
.gitignore
```

See [Adding features](docs/architecture.md) and [Deployment](docs/deployment.md) (currently in Thai).

## Getting started with Docker / Dockge

```bash
git clone https://github.com/NsamaX/suwisa.git
cd suwisa
cp .env.example .env
mkdir -p data backups
```

Fill in `.env`:

```dotenv
DISCORD_TOKEN=<Bot token>
DISCORD_GUILD_ID=<Server ID>
ALLOWED_USER_IDS=<Your user ID>
RECEIPT_CHANNEL_IDS=<Channel ID>
```

Enable Developer Mode in Discord, then right-click the relevant user, server, or channel to copy its ID.
User and channel allowlists accept comma-separated IDs.
The server ID and both allowlists are required. The bot will not start with empty allowlists and does not accept images through DMs.

Enable **Message Content Intent** in the Developer Portal and invite the bot with the `bot` and `applications.commands` scopes.
Required permissions: View Channels, Send Messages, Embed Links, and Read Message History. Attach Files can be included for future exports.
Use a regular text channel; this version does not automatically configure the Send Messages in Threads permission.

```bash
docker compose up -d --build
docker compose logs -f --tail=100 suwisa
```

The container runs as UID/GID `1000:1000`. Bind-mounted directories must be writable by this user.
No ports are published. The bot connects outbound to Discord through the Gateway.

## Local development and image scanning

Use Python 3.12 and Tesseract 5 with the `tha` and `eng` language models:

```bash
# Debian / Ubuntu
sudo apt-get install tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
pip install --no-deps -e .
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` and set `TESSERACT_CMD` / `TESSDATA_DIR` in `.env`.
The language directory must contain `tha.traineddata` and `eng.traineddata` from [Tesseract tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast).

```bash
# No Discord token needed. JSON may contain personal data; keep output in .temp only.
suwisa-receipt .temp/example.jpg
# Start the bot after configuring .env.
suwisa
```

## Testing

```bash
ruff check .
ruff format --check .
pytest -q
# Include real OCR on synthetic images; requires installed language models.
RUN_OCR_TESTS=1 pytest -q
```

In PowerShell, set `$env:RUN_OCR_TESTS='1'` before running `pytest`.
CI tests OCR with synthetic images, builds the Docker image, and checks the language models inside the container.
Tests do not connect to Discord and require no GitHub Actions secrets.

## References

- [discord.py cogs](https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html)
- [Discord Gateway](https://docs.discord.com/developers/events/gateway)
- [Tesseract image quality](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html)
- [SQLite Online Backup API](https://www.sqlite.org/backup.html)
- [Docker Compose production](https://docs.docker.com/compose/how-tos/production/)
