# Tepi Upgrade — Level 2 Prompts, Deck 3, Tepi Web PWA & Chip Polish

Worktree: `/tmp/tepi-upgrade`, branch `tepi-upgrade` (based on `main` at `a8122df`).
`~/Work/tepi` and `~/.local/share/tepi/tepi.sqlite` were never modified.

## Summary of Changes

### Phase 1 — Data Model, Level 2 Engine & Deck 3
- Extended `deck/words.schema.json` with required `sentenceGloss` and optional `cloze` and `note`.
- Backfilled `sentenceGloss` (and concise grammar/affix `note` entries) across all 71 words in `deck/words.json` and 40 words in `deck/words-2.json`.
- Added `make_cloze` (`tepi/sentence.py`) and `card_prompt` (`tepi/engine.py`):
  - New/rest cards and review rungs 0–2 → `word` (`BM → EN`)
  - Review rungs 3–4 → `cloze` (fill-in-the-blank Malay + English sentence hint; falls back to `reverse` for 1-token sentences)
  - Review rung 5+ → `reverse` (`EN → BM`)
- Extended `card_payload` with `promptMode`, `cloze`, `intervalIndex`, `ladderLength`, `sentenceGloss`, and `note`.
- Added `tepi export [--out PATH]` and `tepi import PATH [--replace]` using the `tepi-progress-v1` JSON snapshot format.
- Authored `deck/words-3.json` (40 everyday Peninsular Malaysia words, casual/neutral pairs, and 5 root families: `kerja`, `cakap`, `bayar`, `masak`, `baca`) and `deck/index.json`.
- Added `tests/test_deck3.py` and `tests/test_level2.py` (98 total unit tests).

### Phase 2 — Tepi Web PWA (`web/`)
- Built a zero-dependency static PWA (`web/index.html`, `web/styles.css`, `web/js/engine.js`, `web/js/store.js`, `web/js/app.js`, `web/manifest.webmanifest`, `web/sw.js`, `web/icon.svg`).
- Four calm editorial tabs: **Today** (Level 2 cloze/reverse/word cards, rung dots, keyboard shortcuts `Space`/`1`/`2`/`3`, optional `ms-MY` SpeechSynthesis), **Families** (11 interactive root families), **Garden** (settled/in-play progress + 28-day activity grid), and **Settings** (pacing, dark/light/system theme, JSON export/import compatible with `tepi export`/`tepi import`).
- Verified `web/js/engine.js` against all 151 curriculum words with Node.

### Phase 3 — Omarchy Bar Chip Polish (`plugin/BarWidget.qml`)
- Bar label stays quiet (`lemma` in word mode; blanked cloze or English cue in Level 2 review modes so the bar does not spoil the answer).
- Upgraded popup card with mode + daily counter (`cur/total`), rung dots (`● ● ● ○ ○`), register badge, `sentenceGloss`, `note`, keyboard shortcuts (`1`/`2`/`3`/`Esc`), and a quiet `Open Tepi Web →` link.

## Pending Your Explicit Approval
1. **DBP Attestation for Deck 3:** Per `AGENTS.md` Hard Rule 4, `tepi check --deck-file deck/words-3.json` and `tepi thesaurus --deck-file deck/words-3.json` were **not** run. Once you say yes, we can run them to attest all 40 Deck 3 lemmas in `deck/kamus.json` and `deck/tesaurus.json`.
2. **Merge & Rescan:** Merging `tepi-upgrade` into `main` in `~/Work/tepi` and running `omarchy-shell shell rescanPlugins` to activate the polished chip.
3. **Vault Sync:** Updating `Projects/Tepi.md` in your Obsidian vault to reflect Phase 4, Deck 3, Level 2 prompts, and Tepi Web.
