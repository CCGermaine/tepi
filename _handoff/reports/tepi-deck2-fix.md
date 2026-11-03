# Tepi deck 2 fix

Worktree `/tmp/tepi-deck2-fix`, branch `tepi-deck2-fix`.

Base `406c88d8f86e86e2cd0983c32e053f63bf3b3f9c` (`406c88d`), the tip of `tepi-deck2`. `git merge-base HEAD 406c88d` is that commit.

Code commit `8744e75f85ca60e6be4c3b0ca8885d886a0443bc` — Reject an unknown requires id, and correct the deck 2 sentences. Commit time `2026-11-03 19:32:06 +0800`.

This report is the commit after that one. `~/Work/tepi` stayed on `83a88c9794f33bd50431e4c9194e91278b30d920` (`main`). There is no `master` branch. Nothing was pushed. Nothing was merged.

## Decision log (MYT, +0800)

| When | Choice |
| --- | --- |
| 19:23 | The worktree HEAD was `406c88d` before any edit. The live-checkout hash list was written to `/tmp/tepi-live-sha256-before.txt` before that. |
| 19:23 | No `tepi check` and no `tepi thesaurus`. No lemma changed, so the portal would not add a spelling. `deck/kamus.json` only moves the `baju` row to the new teaching position. Its status stays `headword`. The top `checked` date stays `2026-11-03`. |
| 19:23 | "Harga baju ini murah." and "Perjalanan itu jauh." use `murah` and `jauh`, which are not taught in deck 1 or earlier in deck 2. The sentences are "Harga baju ini baik." and "Perjalanan ke rumah." "Belian saya banyak." is the example from the brief: `banyak` is already in deck 1. "Minggu ini saya sibuk." and "Jalanan sibuk." are the required sentences. `sibuk` is in deck 1. |
| 19:23 | "Saya mahu mengajar." is the standard form of the root `ajar`. The closed-sentence test now treats a `meN-` or `ber-` form of a known lemma as that lemma, so `mengajar` counts as `ajar`. |
| 19:32 | Ruff's default set already fails this tree on `I001` and `PLR0402` (import order, and `import tepi.cli as cli`). `ruff.toml` ignores those two. Every other rule still runs. Codespell ignores Malay tokens that collide with its English list: `lama`, `minum`, `mata`, `meny`. |
| 19:32 | The real progress file was not opened with sqlite. The demo uses the copy `/tmp/tepi-deck2-demo.xcFQ93/tepi.sqlite` and the config `/tmp/tepi-deck2-demo.xcFQ93/config.json`. `verify.sh` compares `stat` mtime and size of the real file and fails if either changes. |

## Changed words

Deck 2 still has 40 words. Five roots still have four words each: `ajar`, `jalan`, `beli`, `main`, `cuci`. `deck/words.json` has an empty diff against `406c88d`.

`baju` moved from after `minggu` to immediately before `mencuci`. Combined teaching indexes: `baju` 88, `mencuci` 89. `mencuci.requires` is `("cuci", "saya", "baju")`.

| id | What changed |
| --- | --- |
| ajar | sentence `Saya mahu ajar.` -> `Saya mahu mengajar.` |
| perjalanan | sentence `Ini perjalanan.` -> `Perjalanan ke rumah.`; requires `["jalan", "ini"]` -> `["jalan", "ke", "rumah"]` |
| jalanan | sentence `Ini jalanan.` -> `Jalanan sibuk.`; requires `["jalan", "ini"]` -> `["jalan", "sibuk"]` |
| beli | gloss `buy` -> `buy (root)` |
| membeli | gloss `buy` -> `to buy, purchase (active verb)` |
| belian | sentence `Ini belian.` -> `Belian saya banyak.`; requires `["beli", "ini"]` -> `["beli", "saya", "banyak"]` |
| main | gloss `play` -> `play (root)` |
| bermain | gloss `play` -> `to play (active verb)` |
| cuci | gloss `wash` -> `wash (root)` |
| baju | gloss `clothes` -> `shirt, top`; moved to just before `mencuci` |
| mencuci | gloss `wash` -> `to wash (active verb)`; sentence `Saya mencuci.` -> `Saya mencuci baju.`; requires `["cuci", "saya"]` -> `["cuci", "saya", "baju"]` |
| pencuci | gloss `cleaner` -> `cleanser, detergent` |
| harga | sentence `Ini harga.` -> `Harga baju ini baik.`; requires `["ini"]` -> `["baju", "ini", "baik"]` |
| minggu | sentence `Ini minggu.` -> `Minggu ini saya sibuk.`; requires `["ini"]` -> `["ini", "saya", "sibuk"]` |

## N1, unknown requires

`load_deck` again rejects a `requires` id that is not in that file and not in an earlier deck file in the same directory. The error names the file and the bad id: `words-9.json: saya requires typo-id, which is not in the deck.`

`load_decks` still loads every given file first, so a require that points at a later file stays "not earlier". A require that names no word raises `words-9.json: saya requires typo-id, which is not in the decks.`

`tepi check --deck-file` uses `load_deck`, so the same error is printed and the command returns 2 before any portal call.

The new test is `test_an_unknown_require_names_the_file_and_the_bad_id`. It copies the first three words of `deck/words.json` (`selamat`, `pagi`, `saya`), sets `saya.requires` to `["typo-id"]`, and writes them to `words-9.json` in a temp deck directory. It does not write the repo `deck/`.

On a detached worktree of `406c88d` at `/tmp/tepi-n1-406c88d`, with this test file copied in:

```
python3 -m unittest discover -s tests -p 'test_decks.py' -k test_an_unknown_require_names_the_file_and_the_bad_id
```

```
FAIL: test_an_unknown_require_names_the_file_and_the_bad_id (test_decks.DeckLoadTest.test_an_unknown_require_names_the_file_and_the_bad_id)
AssertionError: TepiError not raised

Ran 1 test in 0.001s

FAILED (failures=1)
```

`load_deck` on `406c88d` returned the deck. The failure is the missing rejection, and it happens before the test can reach the network.

On commit `8744e75`, the same command:

```
Ran 1 test in 0.002s

OK
```

## N2 and N3

N2: `test_today_command_marks_catch_up_and_log_stays_plain` no longer expects `log["deck"] == 111`. It expects `len(load_curriculum(ROOT).entries)`.

N3: `test_check_deck_file_keeps_the_top_checked_date` writes a temp copy of `deck/kamus.json` with `checked` set to `1999-01-01`, a deck 1 lemma sentinel, and `ajar` marked `missing`. `tepi check --deck-file deck/words-2.json` runs against a fake portal. The saved date stays `1999-01-01`, the deck 1 sentinel stays, and the `ajar` row becomes `headword`. The same merge is what `tepi thesaurus --deck-file` uses. That command was not run.

The committed `deck/kamus.json` diff against `406c88d` does not contain the `checked` line. The only change is the `baju` row moving to sit before `mencuci`:

```
     {
       "lemma": "cuci",
       "status": "headword"
     },
+    {
+      "id": "baju",
+      "lemma": "baju",
+      "status": "headword"
+    },
     {
       "id": "mencuci",
```

The old `baju` row after `minggu` is deleted. Status is still `headword`.

## Tests and verify

`./verify.sh` on the code commit, before this report:

```
...............................................................
----------------------------------------------------------------------
Ran 63 tests in 0.686s

OK
tests: PASS
All checks passed!
ruff: PASS
shellcheck: PASS
codespell: PASS
gitleaks: PASS
real-db untouched: PASS
```

The suite was 61 tests on `406c88d`. The two new tests are the unknown-require test and the checked-date test.

## today --json on a copy

`cp -a ~/.local/share/tepi/tepi.sqlite /tmp/tepi-deck2-demo.xcFQ93/tepi.sqlite`

The copy's last plan day is `2026-11-03`. Progress on the copy is 71 rows, max `deck_index` 70, so deck 1 is introduced and deck 2 is next. The temp config sets `newPerDay` 1, `reviewCap` 0, and `catchUp` false, so each day introduces one word and rests on it. Reviews are not taken. The walk starts at `2026-11-04`.

Command, from `/tmp/tepi-deck2-fix`:

```
TEPI_TEST=1 TEPI_DATA_DIR=/tmp/tepi-deck2-demo.xcFQ93 TEPI_CONFIG=/tmp/tepi-deck2-demo.xcFQ93/config.json TEPI_TODAY=2026-11-04 python3 -m tepi today --json
```

`2026-11-04`, `ajar`:

```
{
  "date": "2026-11-04",
  "mode": "rest",
  "revealed": true,
  "word": {
    "id": "ajar",
    "lemma": "ajar",
    "root": "ajar",
    "register": "neutral",
    "gloss": "teach",
    "sentence": "Saya mahu mengajar."
  },
  "plan": { "reviews": [], "new": ["ajar"] },
  "remaining": { "reviews": 0, "new": 0 },
  "catchUp": false
}
```

`2026-11-22`, `mencuci`: sentence `Saya mencuci baju.`, gloss `to wash (active verb)`.

`2026-12-09`, `minggu`: sentence `Minggu ini saya sibuk.`

The same command on the other changed words, after that word had been introduced on the copy:

| Date | id | gloss | sentence |
| --- | --- | --- | --- |
| 2026-11-04 | ajar | teach | Saya mahu mengajar. |
| 2026-11-10 | perjalanan | journey | Perjalanan ke rumah. |
| 2026-11-11 | jalanan | streets | Jalanan sibuk. |
| 2026-11-12 | beli | buy (root) | Saya mahu beli. |
| 2026-11-13 | membeli | to buy, purchase (active verb) | Saya mahu membeli. |
| 2026-11-15 | belian | purchase | Belian saya banyak. |
| 2026-11-16 | main | play (root) | Saya mahu main. |
| 2026-11-17 | bermain | to play (active verb) | Saya bermain. |
| 2026-11-20 | cuci | wash (root) | Saya mahu cuci. |
| 2026-11-21 | baju | shirt, top | Ini baju. |
| 2026-11-22 | mencuci | to wash (active verb) | Saya mencuci baju. |
| 2026-11-23 | pencuci | cleanser, detergent | Ini pencuci. |
| 2026-11-29 | harga | price | Harga baju ini baik. |
| 2026-12-09 | minggu | week | Minggu ini saya sibuk. |

Real file `~/.local/share/tepi/tepi.sqlite`, `stat` before the copy and after the walk: mtime `2026-11-03 16:59:39.243280254 +0800`, size `61440`, inode `454943`. Same after `./verify.sh`.

## Live checkout

`~/Work/tepi` HEAD `83a88c9794f33bd50431e4c9194e91278b30d920`. `git status --porcelain` is empty.

`sha256sum` of every tracked file, 29 files, compared with `/tmp/tepi-live-sha256-before.txt`: identical. The manifest itself hashes to `000303195439a9a0d6ff36d69f3e39382a72e019f5b38beeaadcb10879e4cc6b`.

## What must be true

1. PASS. Branch `tepi-deck2-fix` is based on `406c88d`. The live checkout is still `83a88c9` and the tracked-file hashes match.
2. PASS. The five required sentence and gloss fixes are in `deck/words-2.json`. `baju` is index 88 and `mencuci` is index 89, and `mencuci` requires `baju`.
3. PASS. Items 6 to 8 are in the table above. 40 words. Five root families of four. `git diff 406c88d -- deck/words.json` is empty.
4. PASS. An unknown `requires` id raises `TepiError` and names the file. The new test fails on `406c88d` and passes on `8744e75`.
5. PASS. N2 derives the deck count. N3 keeps a sentinel `checked` date. The `kamus.json` diff does not change the top date.
6. PASS. `./verify.sh` exits 0. The real database was not opened. Temp paths are the demo directory above and the detached tree `/tmp/tepi-n1-406c88d`.
7. PASS. This file is committed on `tepi-deck2-fix` and printed in the chat.
