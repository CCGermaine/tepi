# Tepi deck 2

Worktree `/tmp/tepi-deck2`, branch `tepi-deck2`.

Code commit `31e894417f392d16e0dec4fe9b2cd3eb62082f2b` — Teach deck 2 after deck 1, and let check cover every deck file.

This report is the commit after that one. `main` is `83a88c9794f33bd50431e4c9194e91278b30d920`. There is no `master` branch. `tepi-deck2` has no upstream. Nothing was pushed.

## 1. Files changed

| Commit | Files |
| --- | --- |
| `31e8944` | `AGENTS.md`, `README.md`, `deck/kamus.json`, `deck/words-2.json`, `tepi/cli.py`, `tepi/deck.py`, `tests/test_catchup.py`, `tests/test_deck2.py`, `tests/test_decks.py`, `tests/test_kamus.py` |
| this report | `_handoff/reports/tepi-deck2.md` |

`deck/words.json`, `deck/tesaurus.json`, and `config.json` are not in the diff. `git diff 83a88c9 -- deck/words.json` is empty.

## 2. What changed

- Deck files load in a fixed order: `deck/words.json`, then `deck/words-N.json` by the number in the name. `words-2.json` comes before `words-10.json`. `words.schema.json` is not a deck.
- Ids must be unique across those files. A repeated id raises `The decks repeat the id '…'`.
- A `requires` id must already exist and sit earlier. A missing id says `not in the decks`. A later id says `not earlier in the decks`. A deck 2 word may require a deck 1 id.
- One file may still name an id from an earlier file. `load_deck` only rejects a require that points at a later word in that same file. `load_decks` checks the whole teaching order. The session uses `load_curriculum`.
- Word indexes run from 0 across the combined deck, so deck 2 starts at 71.
- `tepi check` and `tepi thesaurus --deck` read every deck file. `--deck-file PATH` checks that file only. The printed summary is the file just checked. The saved `deck/kamus.json` or `deck/tesaurus.json` keeps the other deck's rows and appends new ids.
- `deck/words-2.json` has 40 words. Five roots have four words each. 37 are `neutral`. `tengok`, `nak`, and `tak` are `casual`.
- The dictionary check stores status only. Deck 1 rows in `deck/kamus.json` are unchanged. Deck 2 rows are appended. The `checked` date is `2026-11-03`.

The check returns an entry kind (`headword`, `phrase`, `derivative`, `missing`), not a noun or verb class. That class comes from the thesaurus, which this build did not run. Glosses are short English meanings for the way the sentence uses the word, as in deck 1. All 40 lemmas came back attested.

The bar widget was not edited. It still calls `tepi today --json`. This branch is not what the bar runs. `omarchy-shell` was not used.

## 3. Tests

Before this work, on `83a88c9`: `Ran 42 tests` and `OK`.

After, in `/tmp/tepi-deck2`:

```
.............................................................
----------------------------------------------------------------------
Ran 61 tests in 0.677s

OK
```

No warnings on that run. An earlier run the same evening, before commit `31e8944`, was `Ran 61 tests in 0.655s` and `OK`.

The 19 new tests were copied onto a `git archive` of `83a88c9` at `/tmp/tepi-main-83a88c9` and run with `python3 -m unittest discover -s tests -p 'test_deck*.py'` before the production change. Result: `Ran 19 tests` and `FAILED (failures=19)`. Each assertion:

| Test | Failure on 83a88c9 |
| --- | --- |
| `test_the_command_lists_deck_one_then_deck_two` | `['tunggu', 'sebentar', 'nanti', 'tadi'] != ['tunggu', 'sebentar', 'nanti', 'tadi', 'ajar']` |
| `test_numbered_deck_files_follow_words_json_by_number` | `deck_paths is missing` |
| `test_new_words_finish_deck_one_before_deck_two` | `load_curriculum is missing` |
| `test_a_repeated_id_across_decks_is_an_error` | `load_decks is missing` |
| `test_a_require_that_is_missing_is_an_error` | `load_decks is missing` |
| `test_a_require_that_points_later_is_an_error` | `load_decks is missing` |
| `test_deck_one_due_dates_stay_when_deck_two_is_added` | `load_curriculum is missing` |
| `test_help_offers_a_single_deck_file` | `'--deck-file' not found in 'usage: tepi check [-h] [--json]'` |
| `test_check_asks_every_deck` | `71 not greater than or equal to 72 : tadi` |
| `test_check_deck_file_asks_that_file_and_keeps_the_other_rows` | `check --deck-file is not accepted (2)` |
| `test_thesaurus_deck_asks_every_deck` | `71 not greater than or equal to 72 : tadi` |
| `test_thesaurus_deck_file_asks_that_file_and_keeps_the_other_rows` | `thesaurus --deck-file is not accepted (2)` |
| seven `test_deck2` content tests | `deck/words-2.json is missing` |

The check and thesaurus tests patch the portal object. They do not open the network. On the old command, `check` asked 71 lemmas and stopped at `tadi`.

## 4. Dictionary check

One portal run, from `/tmp/tepi-deck2`:

`env -u TEPI_TEST -u TEPI_DATA_DIR -u TEPI_TODAY -u TEPI_CONFIG python3 -m tepi check --deck-file deck/words-2.json`

Exit 0. Started `2026-11-03T18:48:54+08:00`, finished `2026-11-03T18:49:25+08:00`. No retry. No `tepi thesaurus` run.

```
Kamus Dewan Perdana  ·  2026-11-03  ·  40 words
headword 27  ·  phrase 0  ·  derivative 13  ·  missing 0

  pelajar     derivative
  pelajaran   derivative
  berjalan    derivative
  perjalanan  derivative
  jalanan     derivative
  membeli     derivative
  pembeli     derivative
  bermain     derivative
  permainan   derivative
  pemain      derivative
  mencuci     derivative
  pencuci     derivative
  cucian      derivative
```

Attested 40. Not found 0. The saved file has 111 rows. The first 71 match the previous `deck/kamus.json` rows. Keys on every row are `id`, `lemma`, and `status`.

`python3 -m tepi check --help` lists `--deck-file`. A full live `tepi check` of all 111 lemmas was not run. The unit tests call `main(["check"])` and `main(["thesaurus", "--deck"])` against a fake portal and record `selamat` … `tadi` … `ajar` (111 lemmas). `main(["check", "--deck-file", …/words-2.json])` records 40 lemmas starting at `ajar` and leaves a deck 1 sentinel row in place.

## 5. Families and the word list

| Root | Words |
| --- | --- |
| ajar | ajar, belajar, pelajar, pelajaran |
| jalan | jalan, berjalan, perjalanan, jalanan |
| beli | beli, membeli, pembeli, belian |
| main | main, bermain, permainan, pemain |
| cuci | cuci, mencuci, pencuci, cucian |

| Lemma | Gloss | Register |
| --- | --- | --- |
| ajar | teach | neutral |
| belajar | learn | neutral |
| pelajar | student | neutral |
| pelajaran | lesson | neutral |
| jalan | road | neutral |
| berjalan | walk | neutral |
| perjalanan | journey | neutral |
| jalanan | streets | neutral |
| beli | buy | neutral |
| membeli | buy | neutral |
| pembeli | buyer | neutral |
| belian | purchase | neutral |
| main | play | neutral |
| bermain | play | neutral |
| permainan | game | neutral |
| pemain | player | neutral |
| cuci | wash | neutral |
| mencuci | wash | neutral |
| pencuci | cleaner | neutral |
| cucian | laundry | neutral |
| buku | book | neutral |
| kereta | car | neutral |
| bas | bus | neutral |
| kedai | shop | neutral |
| harga | price | neutral |
| wang | money | neutral |
| ibu | mother | neutral |
| ayah | father | neutral |
| anak | child | neutral |
| sekolah | school | neutral |
| guru | teacher | neutral |
| sakit | ill | neutral |
| ubat | medicine | neutral |
| hujan | rain | neutral |
| minggu | week | neutral |
| baju | clothes | neutral |
| kasut | shoe | neutral |
| tengok | look | casual |
| nak | want | casual |
| tak | not | casual |

## 6. Real database

`~/.local/share/tepi/tepi.sqlite`

| | sha256 | mtime |
| --- | --- | --- |
| Before (`2026-11-03T18:34:08+08:00`) | `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151` | `2026-11-03 16:59:39.243280254 +0800` |
| After the code commit (`2026-11-03T18:54:09+08:00`) | `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151` | `2026-11-03 16:59:39.243280254 +0800` |
| After the fresh suite (`2026-11-03T18:57:27+08:00`) | `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151` | `2026-11-03 16:59:39.243280254 +0800` |

Same hash and same mtime. The file was not opened except by `sha256sum` and `stat`.

## 7. Demo on a copy

`cp -a` into a `mktemp` directory. `TEPI_DATA_DIR` pointed at that directory. The command was `python3 -m tepi` from `/tmp/tepi-deck2`. The copy was deleted afterward.

`TEPI_TODAY=2026-11-03` `today --json` returned the plan already stored that morning. Mode `rest`, word `tadi`, reviews `lapar`, `ya`, `di`, `perlu`, new `["tadi"]`, `catchUp` false. The engine does not rebuild a stored plan, so deck 2 was not inserted into 3 November.

`log` on that same copy:

```
Deck 111  ·  in play 71  ·  settled 0  ·  not yet 40
```

`selamat` was still due `2026-11-06`, introduced `2026-09-29`. `tadi` was still due `2026-11-04`, introduced `2026-11-03`. Comparing every deck 1 progress row before and after: 0 rows changed.

On the same copy, `TEPI_TODAY=2026-11-04` `today --json` queued the first deck 2 words after deck 1: `plan.new` was `["ajar", "belajar"]`. Twelve deck 1 reviews were due and `catchUp` was true, which is the existing catch-up cap. The new rows were `ajar` at deck index 71 and `belajar` at deck index 72, both introduced `2026-11-04` and due `2026-11-05`. Deck 1 rows were still unchanged. Then the copy was deleted.

## 8. What must be true

1. PASS. `deck/words-2.json` has 40 schema-valid words, five root families of four, and no deck 1 lemma or id. Proof: `test_deck2` in the 61 passing tests, and the family table above.
2. PASS. Every deck 2 lemma is attested. Proof: the check summary (`missing 0`) and 40 new rows in `deck/kamus.json`, none with status `missing`.
3. PASS. Deck 2 is introduced only after deck 1, and deck 1 progress is kept. Proof: `test_new_words_finish_deck_one_before_deck_two`, `test_deck_one_due_dates_stay_when_deck_two_is_added`, and the copy demo (0 deck 1 rows changed; 4 November queues `ajar`, `belajar`).
4. PASS. `tepi check` and `tepi thesaurus --deck` cover every deck, and `--deck-file` checks one. Proof: `--help`, the live `--deck-file` summary, and the unit tests that call `main(["check"])` and `main(["thesaurus", "--deck"])` with a fake portal. A live portal check of all 111 lemmas was not run.
5. PASS. `deck/words.json` is unchanged (`git diff 83a88c9 -- deck/words.json` empty). The real sqlite hash and mtime match section 6.
6. PASS. `~/Work/tepi` stayed on `83a88c9794f33bd50431e4c9194e91278b30d920` with an empty `git status --porcelain`. sha256 of `tepi/*.py`, `config.json`, and `deck/*.json` matched before and after:

```
c4d66fa75549681e0647595fcb2cc49ae15e7bec4609f64b74db648da2ec309a  tepi/cli.py
152df0913acb190295890b1b62f063961eabdb56ef9636604fe9fe105bcc663f  tepi/db.py
ebfd1d08e4edb14b8cd5587f80a81a4f069e71931f1cb1a39430d3edf05a1e22  tepi/deck.py
fe35e58f68214f921a6361382f7a5ce2962932c8e8dbbdcef75cc4ed8061fbd6  tepi/engine.py
5f7d1914bba8698a373dc33f03cd82ea3baae8a2ed28cdc526f94ff110c29c4f  tepi/__init__.py
2f37fa5a3c8623b52662dbb9e5bc303348864ab1c2a0d9bf67adfbaca62c95f7  tepi/kamus.py
9b30916bc9280441ab59c03c6117ca459de03b87c5e829c2551c34c126b08370  tepi/__main__.py
0680bbb12aedf310bf1050384494dbf890ac63147ad469007ada89504997f928  tepi/tesaurus.py
150f0ce3217784ed6a3484ec1f2921ee31be9c9e1006ce96cb4db3d091514da5  config.json
aa13767842325a9cd1ce818c7a6430cd7de4705e08926d396f249556d56016f3  deck/kamus.json
169c0a820f003dbd27c9cbf1be5a000335165ee6b3444a8acbf63d9cd8772eef  deck/tesaurus.json
54313f574f962d6a0286cc07219b9c5d3c75d3f154087c093b8ff5feb4a8e80c  deck/words.json
c5828bb98f0670b8ade20b7b4cf2e438cfcb337370ebec3da4afb8b05dbcd2a5  deck/words.schema.json
```

7. PASS. 61 tests passed. The work is on `tepi-deck2` in `/tmp/tepi-deck2`. `git log main -1` is `83a88c9`. `tepi-deck2` has no upstream. Nothing was pushed.

## 9. Decision log (MYT)

- 2026-11-03T18:34:08+08:00 — `~/Work/tepi` is `main` at `83a88c9`, clean. Record the real log hash and mtime before any edit. Work only in `/tmp/tepi-deck2`. Do not open the real log. One portal run is allowed, and it is `tepi check --deck-file deck/words-2.json`.
- 2026-11-03T18:34:08+08:00 — Teaching order is `words.json`, then `words-N.json` by number. Ids are unique across files. A require must name an earlier word, including a deck 1 id from deck 2. A stored plan is not rebuilt. `newPerDay` still fills the day, so the day that finishes deck 1 may also take the first deck 2 word.
- 2026-11-03T18:48:54+08:00 — Dictionary check of the 40 lemmas. Finished 18:49:25. Headword 27, derivative 13, phrase 0, missing 0. No second run. No thesaurus run. Deck 1 rows in `kamus.json` stay as they were. No definition, citation, or Jawi is stored.
- 2026-11-03T18:52:16+08:00 — Demo on a copy. 3 November keeps the stored plan (`tadi` only) and all 71 deck 1 due dates. 4 November on that copy queues `ajar` and `belajar`. Delete the copy. The real log hash is still `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151`.
- 2026-11-03T18:54:09+08:00 — Commit `31e8944` on `tepi-deck2`. Do not merge into `main`, do not push, do not rescan the bar, and do not open the original log.
- 2026-11-03T18:57:27+08:00 — Fresh `python3 -m unittest discover -s tests` in the worktree: `Ran 61 tests in 0.677s`, `OK`. `~/Work/tepi` is still `83a88c9` with an empty status. Live source sha256 values match the list in section 6. The real log is still `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151`, mtime `2026-11-03 16:59:39.243280254 +0800`. Commit this report. Do not merge and do not push.

## Waiting on Christian

Merging `tepi-deck2` into `main`. Say so in chat before that. Do not push until then. The bar still runs `~/Work/tepi` on `main`, so it will not show deck 2 until that merge.
