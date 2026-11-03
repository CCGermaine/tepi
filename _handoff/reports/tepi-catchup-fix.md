# Tepi catch-up fix

Worktree `/tmp/tepi-catchup-fix`, branch `tepi-catchup-fix`.

Code commit `74dbb176540a985db83ae083e5692fb64ef634d9` — Show the catch-up marker only when the higher cap adds reviews.

This report is the commit after that one. `main` is `197a09a527f0e1140097bd3e02931b819a400a14`. `tepi-catchup` is `65ed8856d93286ec8af5c0ca02b12e4471357d63`. There is no `master` branch. Nothing was pushed.

## 1. What changed

- `TEPI_CONFIG` selects the schedule file. When it is unset, `tepi` still reads the repo `config.json`. The bar does not set it.
- `test_known_days_clear_the_backlog_and_leave_config_untouched`, `test_today_command_marks_catch_up_and_log_stays_plain`, and the engine tests that used to read the repo `config.json` now load a temp file with `catchUp` on. The command tests pass that path in `TEPI_CONFIG`.
- `tests/_guard.py` patches `load_config` so a test that passes the repo `config.json` raises. Each test module imports it before `tepi`. `test_a_test_cannot_open_the_repo_config` checks that the patch fires.
- The `(catch-up)` heading and `"catchUp": true` are stored only when catch-up puts more reviews on the plan than `reviewCap`. Two overdue reviews stay at 2, with the marker off. Twenty overdue reviews stay at 12, with the marker on. Nothing overdue stays unmarked. The number of reviews planned is the same as on `65ed885`.
- `connect()` already reads `PRAGMA table_info(plans)` and runs `ALTER TABLE` only when `catch_up` is missing. `tepi/db.py` is unchanged. The column stays.
- AGENTS.md hard rule 9: builds work in a git worktree under `/tmp`, never in `~/Work/tepi`. The bar widget runs the live checkout against the real database every 60 seconds.

```diff
--- a/AGENTS.md
+++ b/AGENTS.md
@@ -30,3 +30,4 @@ Tests and manual runs must set `TEPI_DATA_DIR` to a temp folder (and `TEPI_TODAY
 6. Run `python3 -m unittest discover -s tests` before reporting done. If a `_handoff/reports/` folder exists, write the report there.
 7. Bug-to-lint-rule: when the same bug or mistake shows up a second time, add an automatic check (lint rule, test, or guard script) that fails on it, rather than a note. Show that the check fails on the old code.
 8. Keep changes small, one feature per build. No new dependencies.
+9. Builds work in a git worktree under /tmp, never in ~/Work/tepi. The bar widget runs the live checkout against the real database every 60 seconds.
```

## 2. Tests

Worktree, `config.json` has `"catchUp": true`. `TEPI_DATA_DIR` was a temp directory. `TEPI_TODAY=2026-11-03`.

```
Ran 41 tests in 0.443s
OK
```

Second copy `/tmp/tepi-fix-false`, same code, `"catchUp": false` written only in that copy's `config.json`:

```
Ran 41 tests in 0.436s
OK
```

Same suite on a copy of `65ed885` at `/tmp/tepi-65ed885-false`, with `"catchUp": false` in that copy:

```
FAIL: test_known_days_clear_the_backlog_and_leave_config_untouched
AssertionError: 4 not greater than 4

FAIL: test_today_command_marks_catch_up_and_log_stays_plain
AssertionError: False is not true

Ran 37 tests in 0.324s
FAILED (failures=2)
```

Those two tests on `65ed885` read the repo `config.json`. With catch-up off, the backlog day plans 4 reviews, and `today --json` reports `"catchUp": false`.

## 3. Marker, fail on 65ed885

New tests, imported against `/tmp/tepi-at-65ed885/tepi/engine.py` and `cli.py` (that tree is `65ed885` with its `.git` file removed). `TEPI_DATA_DIR` was a temp directory.

```
test_catch_up_on_with_nothing_overdue_leaves_the_marker_off ... ok
test_catch_up_on_with_two_overdue_leaves_the_marker_off ... FAIL
test_catch_up_on_with_twenty_overdue_marks_twelve ... ok

FAIL: test_catch_up_on_with_two_overdue_leaves_the_marker_off
AssertionError: True is not false

Ran 3 tests in 0.003s
FAILED (failures=1)
```

On `65ed885`, nothing overdue already leaves `catch_up` false, so that test passes. Two overdue sets `catch_up` true even though the plan has 2 reviews, which is why it fails. Twenty overdue already plans 12 and sets the marker, so that test passes. On `74dbb17` all three pass inside the 41.

## 4. Live checkout, before and after

Before any edit, and again at 2026-11-03 17:29:46 +08:00:

| Check | Value |
| --- | --- |
| `git -C ~/Work/tepi rev-parse HEAD` | `65ed8856d93286ec8af5c0ca02b12e4471357d63` |
| branch | `tepi-catchup` |
| `git status --porcelain` | empty |
| `tepi/cli.py` | `ec3481c041ac816f5e8bc271bee152a22f09de0e1809ac5ee61fb17950f61814` |
| `tepi/db.py` | `152df0913acb190295890b1b62f063961eabdb56ef9636604fe9fe105bcc663f` |
| `tepi/deck.py` | `ebfd1d08e4edb14b8cd5587f80a81a4f069e71931f1cb1a39430d3edf05a1e22` |
| `tepi/engine.py` | `5ff053c1f19f493431a5df446393c1f76fcd32c7e85bcfd935047022974e7fe3` |
| `tepi/__init__.py` | `5f7d1914bba8698a373dc33f03cd82ea3baae8a2ed28cdc526f94ff110c29c4f` |
| `tepi/kamus.py` | `2f37fa5a3c8623b52662dbb9e5bc303348864ab1c2a0d9bf67adfbaca62c95f7` |
| `tepi/__main__.py` | `9b30916bc9280441ab59c03c6117ca459de03b87c5e829c2551c34c126b08370` |
| `tepi/tesaurus.py` | `0680bbb12aedf310bf1050384494dbf890ac63147ad469007ada89504997f928` |
| `config.json` | `150f0ce3217784ed6a3484ec1f2921ee31be9c9e1006ce96cb4db3d091514da5` |

`__pycache__` was ignored. The before and after hashes match.

## 5. Real log

`~/.local/share/tepi/tepi.sqlite`

| | sha256 | mtime |
| --- | --- | --- |
| Before | `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151` | `2026-11-03 16:59:39.243280254 +0800` |
| After (17:29:46 +08:00) | `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151` | `2026-11-03 16:59:39.243280254 +0800` |

Size stayed 61440. Commands that named this path:

- `stat` and `sha256sum`, before and after, to record mtime and the hash
- one `cp` into `/tmp/tmp.jZL8Zj2At0/tepi.sqlite` for the demo

No `sqlite3` and no `python` opened that path. The hash and mtime are the same, so the bar's 60-second `today --json` did not write the file during this build. Today's plan was already stored, and the live `connect()` returns before `ALTER TABLE` when `plans.catch_up` is already there.

## 6. Demo on the copy

From `/tmp/tepi-catchup-fix`, modules `tepi/cli.py` and `tepi/engine.py` in that worktree. `TEPI_DATA_DIR=/tmp/tmp.jZL8Zj2At0`, `TEPI_TODAY=2026-11-03`. `TEPI_CONFIG` unset, so the worktree `config.json` (`"catchUp": true`) was the schedule.

`tepi today --json`: `"catchUp": false`. `plan.reviews` has 4 words: `lapar`, `ya`, `di`, `perlu`. `mode` is `rest`. `remaining.reviews` is 0.

`tepi today` heading: `2026-11-03  resting`. There is no `(catch-up)` marker.

The copy already had a plan for 2026-11-03. `ensure_plan` returns that stored plan. Its `catch_up` value is 0, so the marker stays off. This run does not build a new day.

## 7. What must be true

1. PASS. The suite is 41 OK with `"catchUp": true` and 41 OK with `"catchUp": false`. On `65ed885` the false run is `FAILED (failures=2)`.
2. PASS. The marker is off with nothing overdue, off with 2 overdue, and on with 20 overdue (12 planned). On `65ed885` the 2-overdue test fails (`True is not false`). Nothing overdue already passes there. Twenty overdue already passes there.
3. PASS. The AGENTS.md diff above adds hard rule 9.
4. PASS. `~/Work/tepi` is still `65ed885`, status empty, and the sha256 list in section 4 matches the start.
5. PASS. The real log was hashed, statted, and copied. It was not opened. Hash and mtime match, both still the 16:59:39 file.
6. PASS, with one naming note. The code is `74dbb17` on `tepi-catchup-fix` in `/tmp/tepi-catchup-fix`. This report is the following commit. `main` is `197a09a`. `tepi-catchup` is `65ed885`. `git rev-parse master` fails: there is no `master`. `tepi-catchup-fix` has no upstream. Nothing was pushed.

## 8. Waiting on Christian

Merging `tepi-catchup-fix` into `master`, and moving the live checkout onto `master`. There is no `master` branch today. `main` is still `197a09a`. Say so in chat before either move. Do not push until then.

The real log keeps `plans.catch_up`. The live checkout stays on `tepi-catchup` at `65ed885`, which is what the bar runs.

## 9. Decision log (MYT)

- 2026-11-03T17:23:05+08:00 — Record the live checkout at `65ed885`, clean, and the real log hash `acfd6f6f…` at 16:59:39. Add `/tmp/tepi-catchup-fix` on `tepi-catchup-fix`. Do not write `~/Work/tepi`. Do not open the real log.
- 2026-11-03T17:23:05+08:00 — Tests that need catch-up load a temp schedule. `TEPI_CONFIG` defaults to the repo `config.json`. The marker is stored only when the chosen plan is longer than `reviewCap`. `connect()` already skips `ALTER TABLE` when the column exists, so `db.py` stays.
- 2026-11-03T17:27:49+08:00 — Worktree suite 41 OK. The false-config copy is 41 OK. `65ed885` with catch-up off is `failures=2`. The 2-overdue marker test fails on `65ed885`. The copy of the real log shows 4 reviews and `catchUp` false, with no marker on the heading. The real log hash is unchanged.
- 2026-11-03T17:28:56+08:00 — Commit `74dbb17`. The live checkout is still `65ed885` and clean.
- 2026-11-03T17:29:46+08:00 — Hash and mtime of the real log still match the start. Commit this note. Do not merge, push, rescan, or open the original log.
