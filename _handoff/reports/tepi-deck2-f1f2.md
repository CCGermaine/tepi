# Tepi deck 2 F1 and F2

Worktree `/tmp/tepi-deck2-f1f2`, branch `tepi-deck2-f1f2`.

Base `e0e98f174f00a29c4b9bb50cda4677adc72e8a3a` (`e0e98f1`), the tip of `tepi-deck2-fix`. `git merge-base HEAD e0e98f1` is that commit.

Code commit `a9a65faf65028bb3b29e107d52cc9296ab60fa6c` — Accept only the active forms deck 2 sentences use. Commit time `2026-11-03 19:48:50 +0800`.

This report is the commit after that one. `~/Work/tepi` stayed on `83a88c9794f33bd50431e4c9194e91278b30d920` (`main`). There is no `master` branch. Nothing was pushed. Nothing was merged.

## Decision log (MYT, +0800)

| When | Choice |
| --- | --- |
| 19:42 | The live-checkout hash list was written to `/tmp/tepi-live-sha256-before.txt` before the worktree. The worktree HEAD was `e0e98f1`. |
| 19:46 | The price sentence is `Ini harga baju.` `requires` stays `["baju", "ini", "baik"]`. The brief said to change nothing else in the deck. `berapa` is not in the sentence. |
| 19:46 | The allow-list is the five derived forms deck 2 sentences use: `mengajar`, `berjalan`, `membeli`, `bermain`, `mencuci`. The closed-sentence walk needs `mengajar`, because `ajar` is the lemma. The other four are also the lemma of their own entry, and the sentences use them, so they are listed too. |
| 19:47 | The new test was applied on a detached worktree of `e0e98f1` at `/tmp/tepi-f2-e0e98f1`. That tree kept `_ACTIVE_PREFIXES`. The checker lives in `tests/test_deck2.py`, so the whole new file would have carried the allow-list with it. `menbaca`, `mebaca`, and `bersaya` each returned true there, and the test failed. |
| 19:48 | `./verify.sh` passed. `verify.sh` was left unchanged. It was added in `8744e75` and has no Verif ownership mark. The mtime check passed on this run, so the optional warning change was not made. |
| 19:48 | No `tepi check` and no `tepi thesaurus`. The real progress file was not opened with sqlite. `stat` before and after the suite matched. |

## F1, price sentence

`git diff e0e98f1 -- deck/` on `a9a65fa`:

```
diff --git c/deck/words-2.json w/deck/words-2.json
index 958b6f8..583ebae 100644
--- c/deck/words-2.json
+++ w/deck/words-2.json
@@ -311,7 +311,7 @@
       "lemma": "harga",
       "root": "harga",
       "gloss": "price",
-      "sentence": "Harga baju ini baik.",
+      "sentence": "Ini harga baju.",
       "register": "neutral",
       "requires": [
         "baju",
```

`deck/words.json` is unchanged. The diff stops at the `requires` context. Those three ids are the same.

## F2, allow-list

`_active_form` in `tests/test_deck2.py` accepts a token when the token is in `_ACTIVE_FORMS` for a lemma already in the known set:

| Root | Form |
| --- | --- |
| ajar | mengajar |
| jalan | berjalan |
| beli | membeli |
| main | bermain |
| cuci | mencuci |

The new test is `test_menbaca_mebaca_and_bersaya_stay_unknown`. It rejects `menbaca`, `mebaca`, and `bersaya`, accepts the five forms above, and walks every deck 2 sentence.

### Fails on e0e98f1

Detached worktree `/tmp/tepi-f2-e0e98f1`, HEAD `e0e98f1`. The test method was inserted. `_ACTIVE_PREFIXES` stayed. Temp data dir `/tmp/tepi-f2-base-data.YJ6FCX`, `TEPI_TEST=1`.

The old checker, imported from that tree:

```
menbaca baca True
mebaca baca True
bersaya saya True
mengajar ajar True
```

```
python3 -m unittest discover -s tests -p 'test_deck2.py' -k 'test_menbaca_mebaca_and_bersaya_stay_unknown'
```

```
FAIL: test_menbaca_mebaca_and_bersaya_stay_unknown (test_deck2.Deck2ContentTest.test_menbaca_mebaca_and_bersaya_stay_unknown)
AssertionError: True is not false

Ran 1 test in 0.000s

FAILED (failures=1)
```

The failure is the first line, `self.assertFalse(_active_form("menbaca", {"baca"}))`. `mebaca` and `bersaya` are the same checker, shown in the three-line probe above. That worktree is dirty and is not a commit.

### Passes on a9a65fa

Same command, from `/tmp/tepi-deck2-f1f2` at `a9a65fa`, `TEPI_TEST=1`, `TEPI_DATA_DIR=/tmp/tepi-f1f2-pass.Xguu75`:

```
Ran 1 test in 0.002s

OK
```

## Tests and verify

`./verify.sh` on the code commit, before this report. Environment `TEPI_TEST=1` and `TEPI_DATA_DIR=/tmp/tepi-f1f2-verify.CZZRwx`. The suite's own databases are `tempfile.TemporaryDirectory` paths, removed when each test ends.

```
................................................................
----------------------------------------------------------------------
Ran 64 tests in 0.699s

OK
tests: PASS
All checks passed!
ruff: PASS
shellcheck: PASS
codespell: PASS
gitleaks: PASS
real-db untouched: PASS
```

The suite was 63 tests on `e0e98f1`. The new one is `test_menbaca_mebaca_and_bersaya_stay_unknown`.

Real file `~/.local/share/tepi/tepi.sqlite`, `stat` before and after the suite: mtime `2026-11-03 16:59:39.243280254 +0800`, size `61440`, inode `454943`. Same after `./verify.sh`. No `sqlite3` command and no `cp` of that file. This change does not read a progress log.

## Live checkout

`~/Work/tepi` HEAD `83a88c9794f33bd50431e4c9194e91278b30d920`. `git status --porcelain` is empty.

`sha256sum` of every tracked file (`git ls-files -z | xargs -0 sha256sum | sort -k2`), 29 files, compared with `/tmp/tepi-live-sha256-before.txt`: identical. The manifest itself hashes to `bff1badd856f68e5088376c68dbb0fe60f9c6fbbd2b63c966cfa99bcad8a2331`.

## What must be true

1. PASS. Branch `tepi-deck2-f1f2` is based on `e0e98f1`. The live checkout is still `83a88c9` and the tracked-file hashes match.
2. PASS. `git diff e0e98f1 -- deck/` is the one sentence line above.
3. PASS. `_active_form` uses the allow-list. `menbaca`, `mebaca`, and `bersaya` fail the new test on `e0e98f1` and pass on `a9a65fa`. The same test walks every deck 2 sentence.
4. PASS. `./verify.sh` exits 0. The real database was not opened. Temp paths are `/tmp/tepi-f1f2-verify.CZZRwx`, `/tmp/tepi-f1f2-pass.Xguu75`, and `/tmp/tepi-f2-e0e98f1` with `/tmp/tepi-f2-base-data.YJ6FCX`.
5. PASS. This file is committed on `tepi-deck2-f1f2` and printed in the chat.
