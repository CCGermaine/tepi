# Tepi phase 4 — root cousins, settled-word sentence, workspace prompt

Worktree `/tmp/tepi-phase4`, branch `tepi-phase4`. Base `366f1aa37156f60fe945a06e5cc0d2e7bd55eea3` (`366f1aa`, tip of `main`). `git merge-base HEAD 366f1aa` is that commit.

Three increment commits, in order, each with tests that fail on `366f1aa`:

| # | Commit | Subject |
| --- | --- | --- |
| 1 | `468ab16ebe1664696c3b73d27fa463a750ca8549` | Surface root cousins in the command and the chip |
| 2 | `b4e1bd3dd9a48671eb0709997e490ea0bff90f6b` | Build a prompt sentence from settled words only |
| 3 | `a43c70c08973df9c97261379b0740c578f7ecefb` | Follow the workspace with a read-only --about prompt hint |

This report is the commit after those three. `~/Work/tepi` stayed on `366f1aa` (`main`), `git status --porcelain` empty. Nothing pushed, nothing merged. The live bar widget kept running the untouched checkout against the real log throughout.

## Decision log (MYT, +0800)

Times are approximate except the anchored end; choices are in the order they were made.

| When | Choice |
| --- | --- |
| ~10:42 | Read-only setup: `~/Work/tepi` clean, `main` at `366f1aa`. Recorded the sha256 of all 38 tracked files (`live-sha256-before.txt`) and the real DB `stat`/sha256 before any work. Created the worktree with `git worktree add -b tepi-phase4 /tmp/tepi-phase4 main`. |
| ~10:45 | Baseline `./verify.sh` in the worktree: **64 tests**, all checks PASS. Confirmed the brief's "64 before". |
| ~10:48 | Derived the 6 root families from the deck (read-only): komputer×2; ajar/jalan/beli/main/cuci×4; 89 singleton roots; 111 entries. Cousins = groups of ≥2; singletons have no cousins. |
| ~10:50 | Increment 3 signal investigation (read-only): the shell's own `Workspaces.qml` and `PopupCard.qml` import `Quickshell.Hyprland`; `monitor.activeWorkspace` is the workspace read. `hyprctl workspaces` shows this machine's workspaces are unnamed numbers (`1`,`2`,`4`,`5`). So a clean read-only hook exists, but a number has no honest lexical relation to a Malay word. Chose: wire the real hook AND implement `--about`; the hint matches a settled lemma/root or falls back. No invented number→word mapping. |
| ~10:52 | Resolved a wording conflict in the brief: line 38 says "never … cp" the real DB, line 39 and increment 2 say to prove on a `cp` copy "exactly as the deck2 briefs did". The deck2/deck2-fix briefs and reports used `cp -a` into mktemp + `TEPI_TEST=1` + temp `TEPI_CONFIG`. Followed that precedent: the real file is only read by `cp`/`stat`/`sha256sum`, never opened with sqlite, never written; all crafting happens on the copy, deleted afterward. |
| ~10:55 | Increment 1: `cousin_families`/`cousins_of` in the engine (deck-only, no log). `tepi cousins [id] [--json]` handled before `_session()` so it never opens the DB. `card_payload(card, deck=None)` keeps the one-arg call used by `test_catchup.py`; the chip shows a dim "cousins: …" caption. 9 tests. |
| ~10:58 | Increment 2: moved the tokenizer + function-word and active-form allow-lists from `tests/test_deck2.py` into `tepi/sentence.py` (shared, not duplicated); `unknown(..., active=False)` for the stricter prompt rule. `prompt_sentence` returns the first settled+attested word whose own deck sentence is formable (≤12 tokens, every non-function word a settled lemma). No-op messages, exit 0. 7 tests. |
| ~11:00 | Synthetic settled demo on a `cp` copy: crafted 2 settled words (pagi, saya) via `TEPI_TODAY` + the `knownIntervals` ladder (97 iterations, reviews-only temp config). Prompt `Saya.` validated inside the settled vocabulary. Real DB sha256/mtime identical before/after; copy deleted. |
| ~11:02 | Increment 3: `--about WORD` (lemma or root match prefers a settled cousin; unmatched falls back). Chip reads `Hyprland.focusedMonitor.activeWorkspace.name` and passes it as the hint when the popup opens, showing the sentence as a dim italic line. 7 tests. |
| 11:03 | Final `./verify.sh`: **87 tests**, all checks PASS. Live-checkout sha256 list identical to before. Wrote this report. |

A measurement note: the first "after" hash comparison wrongly showed four files changed. Cause: `git -C ~/Work/tepi ls-files` prints relative paths, but `xargs sha256sum` ran with the shell cwd in `/tmp/tepi-phase4`, so it hashed the worktree files. Recomputed from `~/Work/tepi`: the list is identical, and each of the four files matches its `366f1aa` blob byte-for-byte. The live checkout was never touched.

## Diff summaries

Per increment (`git diff --stat`):

```
-- inc1 (366f1aa..468ab16) --
 plugin/BarWidget.qml  |  15 +++++
 tepi/cli.py           |  67 +++++++++++++++++---
 tepi/engine.py        |  29 +++++++++
 tests/test_cousins.py | 171 ++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 273 insertions(+), 9 deletions(-)

-- inc2 (468ab16..b4e1bd3) --
 tepi/cli.py          |  41 +++++++++++-
 tepi/engine.py       |  42 ++++++++++++
 tepi/sentence.py     |  97 +++++++++++++++++++++++++++
 tests/test_deck2.py  |  88 ++-----------------------
 tests/test_prompt.py | 182 +++++++++++++++++++++++++++++++++++++++++++++++++++
 5 files changed, 365 insertions(+), 85 deletions(-)

-- inc3 (b4e1bd3..a43c70c) --
 plugin/BarWidget.qml |  38 ++++++++++++
 tepi/cli.py          |   3 +-
 tepi/engine.py       |  21 ++++++-
 tests/test_about.py  | 159 +++++++++++++++++++++++++++++++++++++++++++++++++++
 4 files changed, 217 insertions(+), 4 deletions(-)
```

Whole branch `366f1aa..a43c70c`: 8 files, +850 / −93. `git diff 366f1aa..a43c70c -- deck/` is **empty** — no deck content changed. No `*.sqlite` tracked. `tests/test_deck2.py` shrank because its tokenizer moved into `tepi/sentence.py`; its 8 tests still pass unchanged.

## Tests and verify

Before (on `366f1aa`): **64 tests**. After (on `a43c70c`): **87 tests** (+9 cousins, +7 prompt, +7 about).

Final `./verify.sh` (env `TEPI_TEST=1`, `TEPI_DATA_DIR=/tmp/tepi-p4-final.*`):

```
Ran 87 tests in 6.472s

OK
tests: PASS
All checks passed!
ruff: PASS
shellcheck: PASS
codespell: PASS
gitleaks: PASS
real-db untouched: PASS
```

### Fail-on-old evidence

Each new test file was copied into a detached worktree of `366f1aa` at `/tmp/tepi-p4-base` (kept dirty, not committed) and run there. New engine symbols are imported inside the test methods so the file yields genuine per-test failures on the base, not only a collection error.

| Increment | File | On `366f1aa` | On its commit |
| --- | --- | --- | --- |
| 1 | `test_cousins.py` | `Ran 9 tests … FAILED (failures=5, errors=4)` | `Ran 9 tests … OK` |
| 2 | `test_prompt.py` | `Ran 7 tests … FAILED (failures=1, errors=6)` | `Ran 7 tests … OK` |
| 3 | `test_about.py` | `Ran 7 tests … FAILED (failures=2, errors=5)` | `Ran 7 tests … OK` |

Representative failures on the base:

```
# inc1 — the command does not exist on main
FAIL: test_cousins_command_returns_the_family_for_an_id
AssertionError: 2 != 0 : usage: tepi [-h] {today,reveal,log,rate,dict,check,thesaurus} ...
tepi: error: argument cmd: invalid choice: 'cousins'

# inc1 — the engine API does not exist on main
ERROR: test_families_group_by_root_across_both_decks
ImportError: cannot import name 'cousin_families' from 'tepi.engine'

# inc2 — the command does not exist on main
FAIL: test_prompt_with_nothing_settled_prints_the_noop_message
AssertionError: 2 != 0 : ... invalid choice: 'prompt'

# inc3 — the engine API does not exist on main
ERROR: test_about_picks_the_matching_settled_word
ImportError: cannot import name 'prompt_sentence' from 'tepi.engine'
```

The chip payload tests fail on main with `KeyError: 'cousins'` (the field is new). Full transcripts: `inc1-fail-on-old.txt`, `inc2-fail-on-old.txt`, `inc3-fail-on-old.txt` in the session scratch dir.

## Increment 1 — cousins family table

`tepi cousins` (deck-only, no log opened), in root order (first member's teaching index):

| Root | Members (teaching order) | Indices | Count |
| --- | --- | --- | --- |
| komputer | komputer, komputer riba | 42, 43 | 2 |
| ajar | ajar, belajar, pelajar, pelajaran | 71–74 | 4 |
| jalan | jalan, berjalan, perjalanan, jalanan | 75–78 | 4 |
| beli | beli, membeli, pembeli, belian | 79–82 | 4 |
| main | main, bermain, permainan, pemain | 83–86 | 4 |
| cuci | cuci, mencuci, pencuci, cucian | 87, 89, 90, 91 | 4 |

`tepi cousins belajar`:

```
ajar  ·  4 words
  ajar
  belajar
  pelajar
  pelajaran
```

`tepi cousins belajar --json` returns `root: "ajar"` with members `ajar(71), belajar(72), pelajar(73), pelajaran(74)`. An unknown id exits 2 with "The deck has no word '…'." A singleton (`tepi cousins air`) reports "air has no cousins." (`cousins: []` in JSON). The card payload (`today/reveal/rate --json`) carries `word.cousins` (the other lemmas); the chip shows them as a dim caption "cousins: …" below the lemma. Scheduling is unchanged.

## Increment 2 — settled-word prompt

`tepi prompt` with nothing settled (fresh temp DB, temp config):

```
No settled words yet.
```

```json
{ "sentence": null, "word": null, "settled": 0, "message": "No settled words yet." }
```

Exit 0; no progress row is written. When some words are settled but none can form its sentence, it prints "No settled sentence yet." (exit 0). It never raises and never invents spelling: it only returns a sentence already in the deck, validated with the shared tokenizer at ≤12 tokens and `active=False` (every non-function word must itself be a settled, attested lemma).

### Synthetic settled demo (cp copy, real DB never opened)

`cp -a ~/.local/share/tepi/tepi.sqlite` into `mktemp` dir `/home/manny/.hermes/cache/scratch/tepi-p4-settled-demo.hlirawj8`; temp config = repo config with `newPerDay: 0` (reviews only). Crafted via `TEPI_TODAY` + the `knownIntervals` ladder: 97 iterations, final `TEPI_TODAY=2029-12-15`, **2 settled words: pagi, saya**.

`tepi log` on the copy: `Deck 111 · in play 101 · settled 2 · not yet 8`.

`tepi prompt` on the copy:

```
Saya.
```

```json
{ "sentence": "Saya.", "word": { "id": "saya", "lemma": "saya" }, "settled": 2, "message": null }
```

Validation: settled lemmas `{pagi, saya}`; sentence tokens `[saya]`; token count 1 (≤12); unknown (non-settled, non-function) tokens `[]`; every content token is a settled lemma → **PASS**. `saya` is first in teaching order; `pagi`'s sentence "Selamat pagi." needs the still-unsettled `selamat`, so it is correctly skipped. The multi-word case is proven deterministically in `test_prompt_uses_only_settled_words_and_is_short` (`Saya mahu air.`, 3 tokens) and via the CLI in increment 3. The copy was deleted afterward.

## Increment 3 — workspace prompt (what signal, and why)

**Signal used:** the focused monitor's active workspace, read through `Quickshell.Hyprland` (`Hyprland.focusedMonitor.activeWorkspace.name`) in `plugin/BarWidget.qml`. This is the same read-only API the shell's own `Workspaces.qml` uses (`monitor.activeWorkspace`, `Hyprland.workspaces.values`); `Quickshell.Hyprland` is already imported by the shell (`Style.qml`, `PopupCard.qml`, `OverlayWindow.qml`), so it adds **no dependency** and performs **no dispatch**. Verified read-only via `hyprctl workspaces -j`: this machine's workspaces are named `1`, `2`, `4`, `5` — plain numbers, no semantic names.

**Why this shape:** a clean read-only hook exists, so it is wired (the chip passes the workspace name as `--about` when the popup opens and shows the returned sentence as a dim italic line). But a workspace number has no honest lexical relation to a Malay word, and inventing a number→word map would fabricate content the deck does not contain. So `tepi prompt --about WORD` prefers a settled word whose **lemma or root** matches the hint (a root match picks a settled cousin) and otherwise falls back to the first eligible settled word. With today's numeric workspace names the hint matches nothing and the chip rests as before; naming a workspace after a settled word (or root) activates the relation. Nothing is faked: the read is real, the match is real, and the fallback is the plain settled prompt.

`--about` demo (crafted settled temp DB: saya, mahu, air):

```
--about 'air'    -> 'Saya mahu air.' (word air)      # lemma match, 3 tokens
--about 'ajar'   -> 'Saya.' (word saya)              # no ajar cousin settled here -> fallback
--about '2'      -> 'Saya.' (word saya)              # the live workspace number -> fallback
--about 'zzzz'   -> 'Saya.' (word saya)              # unknown hint -> fallback
```

The root-match-picks-a-cousin path is proven in `test_about_a_root_picks_a_settled_cousin` (fixture with settled `belajar`/`pelajar`, `--about ajar` → `belajar`).

**QML caveat (honest):** there is no QML test harness in the repo and no `qmllint` on this machine, and the brief forbids `omarchy-shell`/rescan. The chip changes are presentation-only and mirror the shell's existing patterns; they are verified by inspection and by the CLI tests, **not** live-rendered. The live chip still runs the old code until Christian merges and runs `omarchy-shell shell rescanPlugins`.

## Real DB proof (never opened with sqlite)

`~/.local/share/tepi/tepi.sqlite`, only ever read by `stat`, `sha256sum`, and `cp`:

| | mtime | size | sha256 |
| --- | --- | --- | --- |
| Before | `2026-11-19 00:00:56.052292065 +0800` | 106496 | `efd58c8802611fb22d6c06d67f6315edcbcae3e9fce4abec5e9e1c5b65e06263` |
| After (final verify + demo) | `2026-11-19 00:00:56.052292065 +0800` | 106496 | `efd58c8802611fb22d6c06d67f6315edcbcae3e9fce4abec5e9e1c5b65e06263` |

Identical mtime, size, and hash. Temp paths used: the settled-demo copy `…/tepi-p4-settled-demo.hlirawj8` (deleted), and `mktemp` data dirs for the suites/demos (`tepi-p4-final.*`, `tepi-p4-noop.*`, `tepi-p4-about-demo.*`, etc.). `verify.sh`'s own real-db-untouched check passed on every run.

## Live checkout proof

`~/Work/tepi` HEAD `366f1aa37156f60fe945a06e5cc0d2e7bd55eea3`, `git status --porcelain` empty. sha256 of every tracked file (38 files, `git ls-files -z | xargs -0 sha256sum | sort -k2`, run from `~/Work/tepi`) is **identical** to `live-sha256-before.txt`. The four files this branch edits each match their `366f1aa` blob on the live disk:

```
plugin/BarWidget.qml  67d6575db5eda24ca6516581636f557e83d2bd999bc1d2c02b030c10d07ca9e5
tepi/cli.py           4e83fb4fe317d6bc4581b80c9120d56b5d61666a0edfee2d236b2171c3aa3069
tepi/engine.py        fe35e58f68214f921a6361382f7a5ce2962932c8e8dbbdcef75cc4ed8061fbd6
tests/test_deck2.py   ebf4411d645334e96bcd6e248bd8427c1eb22487f9903d46af2f8bef3060bfe3
```

`git branch -vv`: `main 366f1aa [origin/main]` (unchanged, not ahead); `tepi-phase4 a43c70c (/tmp/tepi-phase4)` (local only, no upstream). Worktrees: `~/Work/tepi [main]`, `/tmp/tepi-phase4 [tepi-phase4]`, `/tmp/tepi-p4-base (detached 366f1aa)` (the dirty fail-on-old tree).

## What must be true

1. **PASS** — Branch `tepi-phase4` is based on `366f1aa` (`merge-base` = base). `~/Work/tepi` unchanged: same HEAD, empty status, identical 38-file sha256 list. Proof: git log + the hash comparison above.
2. **PASS** — Cousins derive from the deck `root` field, ordered by teaching index across both decks (6 families table). `git diff 366f1aa..a43c70c -- deck/` empty. Proof: `tepi cousins` output + empty deck diff.
3. **PASS** — `tepi prompt` uses only settled, attested words, ≤12 tokens; prints "No settled words yet." when nothing is settled; proven on a synthetic settled copy (2 settled, `Saya.`, validation PASS). Proof: test output + demo.
4. **PASS** — Increment 3 uses a real read-only workspace signal (`Quickshell.Hyprland` `focusedMonitor.activeWorkspace.name`, the shell's own read) **and** honestly exposes `--about`; numeric workspace names fall back, no fabricated mapping. Proof: this statement + the QML/CLI code + `--about` tests. (Live chip render is pending Christian's rescan — see caveat; the CLI behavior is fully tested.)
5. **PASS** — Full `./verify.sh` passes (87 tests; ruff/shellcheck/codespell/gitleaks/real-db-untouched all PASS). Real DB never opened with sqlite; stat+sha256 identical before/after. Proof: verify output + DB table.
6. **PASS** — This report is committed on `tepi-phase4` and printed in chat. Proof: `/tmp/tepi-phase4/_handoff/reports/tepi-phase4.md`.
7. **PASS** — Nothing pushed; `main` unchanged at `366f1aa`, not ahead of `origin/main`. Proof: `git branch -vv`.

## Still waiting on Christian's yes

- **Merging `tepi-phase4` into `main`** (the three increments + this report). Not done; needs explicit approval.
- After merge: `omarchy-shell shell rescanPlugins` to load the new chip code (cousins caption + workspace prompt line). The live chip render of increments 1 and 3 is **UNVERIFIED** until then (no QML harness; rescan forbidden in this build).
- Optional, to make the workspace prompt show a related word rather than rest: name a workspace after a settled word or root (e.g. a Hyprland named workspace). Today the numeric names match nothing, by design.

END OF REPORT
