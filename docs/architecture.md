# Adding features

The Discord layer is an adapter. Keep business rules in ordinary Python modules so they can be tested without Discord or a token.

## Dependency direction

`Discord cog -> feature service -> feature models / parser`

The OCR engine implements `OcrEngine`. Storage depends on receipt models. `bot.py` constructs these adapters and injects them; the parser never imports Discord, SQLite, or Tesseract.

## Add a feature

1. Create `src/suwisa/features/<feature>/` with `__init__.py`, `cog.py`, and its models/service modules.
2. Give `cog.py` an `async def setup(bot)` entry point that calls `bot.add_cog(...)`.
3. Add its module name to `FEATURE_EXTENSIONS` in `bot.py`.
4. Add storage migrations if needed. SQLite `PRAGMA user_version` currently equals 1; upgrade existing databases transactionally. Do not drop tables to migrate.
5. Test business rules and authorization before enabling the feature.

Reviewed receipts now store `issuer_bank` and `transaction_type`. The owner's explicit convention is BKK -> expense (including wallet top-ups), KBank/KTB -> income. This is a personal bookkeeping rule, not a universal interpretation of transfers. `classification.py` owns the mapping. Money remains exact decimal strings; fees are separate and not added to amount automatically. Summaries or a full ledger can be added as separate features.

Existing JSON payloads remain readable without a schema change. Old rows are not automatically assigned a bank from incomplete data. Reconfirming the same image/reference can update its classification, but cannot change the reviewed amount/currency. The original row ID and monetary data survive.

## OCR and parsing

- Implement `OcrEngine.read(bytes) -> OcrDocument` and select it in `bot.py` / CLI. Cloud OCR should be an explicit configured provider because it sends receipts outside the machine.
- Add a parser module for each new bank layout; reuse amount/date helpers.
- Prefer missing values and review warnings over guesses. Never infer dates from reference numbers or use the largest number as a total.
- Identify issuing banks from header branding and the supported source-account layout, not arbitrary bank names anywhere in the slip. In particular, a Bangkok Bank receiver on a KBank/KTB slip does not make it a BKK expense.
- Recipient normalization uses recognized identifiers such as `TMNTOPUP` or the wallet name on BKK slips; it does not authenticate a transaction.

## Lifecycle

Allowlist -> attachment limit -> bounded OCR slot -> decode/EXIF normalization -> Thai/English OCR -> parser -> review -> optional save.

One OCR job runs at a time, with at most three users admitted and one job per user. OCR uses a worker thread; each Tesseract subprocess has a timeout (up to three passes per image). Discord heartbeats continue during OCR.

Review state lives in memory for 10 minutes. Database writes happen only on confirmation, with a unique image hash and optional reference scoped to guild + owner. Cancelled, expired or interrupted reviews are not stored. SQL uniqueness protects concurrent writes.

`/receipt` replies ephemerally. Automatic attachment replies appear in the configured channel; use a private bookkeeping channel if needed. Both enforce the same user/guild/channel allowlists. Buttons enforce ownership.

## Boundaries

- No general chat reasoning, ledger, exports, reminders, line-item extraction or bank verification API yet.
- No persistent image archive; design retention and backup together before adding one.
- Health reflects recent Discord readiness/latency, not OCR accuracy. Unhealthy status alone does not restart a Docker container.
- Schema changes can make old images unsuitable for rollback. Back up first and restore a compatible database when necessary.
