# Tepi test-config gap

Worktree `/tmp/tepi-test-config-gap`, branch `tepi-test-config-gap`.

Code commit `bba597d074b5c988467ca33628e485acae40c629` — Refuse the repo config when a test runs tepi.

This report is the commit after that one. `main` is `0df7d3d6703c7e3dbc592aa1e1f28ee2788cd6ca`. There is no `master` branch. `tepi-test-config-gap` has no upstream. Nothing was pushed.

## 1. Which fix

Fix 2. `tests/_guard.py` sets `TEPI_TEST=1` on import. While that variable is set, `tepi` raises if the schedule path is the checkout's `config.json`, and prints `A test opened the repo config at <path>. Pass a temp config instead.` A run that does not set `TEPI_TEST` still uses the repo schedule when `TEPI_CONFIG` is unset.

The reproduction copies `65ed885`'s `tests/test_catchup.py` and adds `import _guard`. That file carries its own `_run()`, and the test copies `os.environ` into the child. The marker set by the guard is what that child sees. The check is three lines in `tepi/cli.py` and four lines in the guard, plus `test_a_subprocess_cannot_open_the_repo_config`. The refusal is raised before `Session.open`, so the command does not open a database.

## 2. Reproduction

`/tmp/tepi-repro-0df7d3d` is `git archive 0df7d3d`. `tests/test_catchup.py` is `65ed885`'s file plus `import _guard` before the `tepi` imports. `TEPI_CONFIG` and `TEPI_TEST` were unset. `TEPI_DATA_DIR` was a temp directory. `TEPI_TODAY=2026-11-03`.

```
test_today_command_marks_catch_up_and_log_stays_plain (test_catchup.CatchUpTest.test_today_command_marks_catch_up_and_log_stays_plain) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.194s

OK
```

That pass is the gap. The test seeds every deck word as overdue and expects `"catchUp": true` and 12 reviews. The repo `config.json` is the schedule that produces that result. The in-process guard does not run inside `python -m tepi`.

The same file on a copy of this worktree, `/tmp/tepi-repro-fixed`, with the fixed `cli.py` and `_guard.py`:

```
test_today_command_marks_catch_up_and_log_stays_plain (test_catchup.CatchUpTest.test_today_command_marks_catch_up_and_log_stays_plain) ... FAIL

======================================================================
FAIL: test_today_command_marks_catch_up_and_log_stays_plain (test_catchup.CatchUpTest.test_today_command_marks_catch_up_and_log_stays_plain)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/tmp/tepi-repro-fixed/tests/test_catchup.py", line 232, in test_today_command_marks_catch_up_and_log_stays_plain
    payload = _run(["today", "--json"], env)
  File "/tmp/tepi-repro-fixed/tests/test_catchup.py", line 253, in _run
    raise AssertionError(completed.stderr)
AssertionError: A test opened the repo config at /tmp/tepi-repro-fixed/config.json. Pass a temp config instead.


----------------------------------------------------------------------
Ran 1 test in 0.060s

FAILED (failures=1)
```

The new test, copied onto a fresh `0df7d3d` tree whose `cli.py` and `_guard.py` are still the old files (`/tmp/tepi-newtest-0df7d3d`), fails because the command exits 0 and prints a card:

```
test_a_subprocess_cannot_open_the_repo_config (test_catchup.CatchUpTest.test_a_subprocess_cannot_open_the_repo_config) ... FAIL

AssertionError: 0 == 0 : {
  "date": "2026-11-03",
  ...
  "catchUp": false
}

Ran 1 test in 0.057s

FAILED (failures=1)
```

On this branch that test is one of the 42 below, and it passes.

## 3. Suite

Worktree `/tmp/tepi-test-config-gap`. `TEPI_TODAY=2026-11-03`. Each run had its own temp `TEPI_DATA_DIR`. `TEPI_CONFIG` pointed at a `/tmp` copy of `config.json`. The worktree `config.json` was left as committed.

`catchUp` true, `TEPI_CONFIG=/tmp/tepi-config-catchup-true.json`, `TEPI_DATA_DIR=/tmp/tmp.0rcrw2ZjYz`:

```
..........................................
----------------------------------------------------------------------
Ran 42 tests in 0.506s

OK
```

`catchUp` false, `TEPI_CONFIG=/tmp/tepi-config-catchup-false.json`, `TEPI_DATA_DIR=/tmp/tmp.Je8NAALLNl`:

```
..........................................
----------------------------------------------------------------------
Ran 42 tests in 0.510s

OK
```

Worktree `config.json` before and after both runs: `150f0ce3217784ed6a3484ec1f2921ee31be9c9e1006ce96cb4db3d091514da5`. Same hash as `~/Work/tepi/config.json`.

## 4. Unmarked `tepi today --json`

From the worktree, `python3 -m tepi today --json`. `TEPI_TEST` unset. `TEPI_CONFIG` unset, so the schedule is the worktree `config.json`. `TEPI_DATA_DIR=/tmp/tmp.G9KqOnE9qe`. `TEPI_TODAY=2026-11-03`. Exit 0.

The same command from `/tmp/tepi-repro-0df7d3d` (code `0df7d3d`, its own temp data dir) printed the same JSON. `diff` was empty.

```
{
  "date": "2026-11-03",
  "mode": "new",
  "revealed": false,
  "word": {
    "id": "selamat",
    "lemma": "selamat",
    "root": "selamat",
    "register": "neutral",
    "gloss": null,
    "sentence": null
  },
  "plan": {
    "reviews": [],
    "new": [
      "selamat",
      "pagi"
    ]
  },
  "remaining": {
    "reviews": 0,
    "new": 2
  },
  "catchUp": false
}
```

A fresh log has nothing overdue, so the marker stays off and the day introduces `selamat` and `pagi`. That is the same card `0df7d3d` builds.

## 5. Live checkout

`~/Work/tepi` before the worktree (2026-11-03 18:03:31 +08:00) and again at 18:06:43 +08:00. `diff` of the two records was empty.

| Check | Value |
| --- | --- |
| `git -C ~/Work/tepi rev-parse HEAD` | `0df7d3d6703c7e3dbc592aa1e1f28ee2788cd6ca` |
| branch | `main` |
| `git status --porcelain` | empty |
| `ahead` | `origin/main` by 5, unchanged from the start |
| `config.json` | `150f0ce3217784ed6a3484ec1f2921ee31be9c9e1006ce96cb4db3d091514da5` |
| `deck/kamus.json` | `aa13767842325a9cd1ce818c7a6430cd7de4705e08926d396f249556d56016f3` |
| `deck/tesaurus.json` | `169c0a820f003dbd27c9cbf1be5a000335165ee6b3444a8acbf63d9cd8772eef` |
| `deck/words.json` | `54313f574f962d6a0286cc07219b9c5d3c75d3f154087c093b8ff5feb4a8e80c` |
| `deck/words.schema.json` | `c5828bb98f0670b8ade20b7b4cf2e438cfcb337370ebec3da4afb8b05dbcd2a5` |
| `tepi/cli.py` | `78de4d1a88b63a4907e9192788e590da82a8ff63527e4fb6afe7cdea770229a2` |
| `tepi/db.py` | `152df0913acb190295890b1b62f063961eabdb56ef9636604fe9fe105bcc663f` |
| `tepi/deck.py` | `ebfd1d08e4edb14b8cd5587f80a81a4f069e71931f1cb1a39430d3edf05a1e22` |
| `tepi/engine.py` | `fe35e58f68214f921a6361382f7a5ce2962932c8e8dbbdcef75cc4ed8061fbd6` |
| `tepi/__init__.py` | `5f7d1914bba8698a373dc33f03cd82ea3baae8a2ed28cdc526f94ff110c29c4f` |
| `tepi/kamus.py` | `2f37fa5a3c8623b52662dbb9e5bc303348864ab1c2a0d9bf67adfbaca62c95f7` |
| `tepi/__main__.py` | `9b30916bc9280441ab59c03c6117ca459de03b87c5e829c2551c34c126b08370` |
| `tepi/tesaurus.py` | `0680bbb12aedf310bf1050384494dbf890ac63147ad469007ada89504997f928` |

`__pycache__` was ignored. The real log at `~/.local/share/tepi/tepi.sqlite` was not opened. Every run set `TEPI_DATA_DIR` to a temp directory.

## 6. What must be true

1. PASS. Verif's reproduction is OK on `0df7d3d` (section 2, 0.194s) and FAIL after the fix, with `A test opened the repo config at /tmp/tepi-repro-fixed/config.json. Pass a temp config instead.` The new test fails on `0df7d3d` (`0 == 0` plus a card) and passes inside the 42.
2. PASS. The suite is 42 OK with `"catchUp": true` (0.506s) and 42 OK with `"catchUp": false` (0.510s). The worktree `config.json` hash stayed `150f0ce3…`.
3. PASS. Unmarked `tepi today --json` on a temp data dir and the repo config exits 0. The JSON matches the same command on `0df7d3d` byte for byte. `catchUp` is false. The new words are `selamat` and `pagi`.
4. PASS. `~/Work/tepi` is still `0df7d3d`, status empty, and the sha256 list in section 5 matches the start.
5. PASS, once this file is committed. The code is `bba597d` on `tepi-test-config-gap` in `/tmp/tepi-test-config-gap`. This report is the following commit. `main` is `0df7d3d`. `tepi-test-config-gap` has no upstream. Nothing was pushed. The worktree stays in place.

## 7. Waiting on Christian

Merging `tepi-test-config-gap` into `main`. `main` is still `0df7d3d`. Say so in chat before that merge. Do not push until then.

## 8. Decision log (MYT)

- 2026-11-03T18:03:31+08:00 — Record `~/Work/tepi` at `0df7d3d`, clean, with the sha256 list in section 5. Add `/tmp/tepi-test-config-gap` on `tepi-test-config-gap`. Do not write the live checkout. Do not open the real log.
- 2026-11-03T18:03:31+08:00 — Use fix 2. The reproduction imports `_guard` and copies `os.environ` into its own `_run`. Set `TEPI_TEST=1` in the guard. Refuse the repo `config.json` in `_session` while that marker is set, before `Session.open`. Leave unmarked runs on the repo schedule.
- 2026-11-03T18:06:01+08:00 — Reproduction on `0df7d3d` is OK (1 test, 0.194s). The same reproduction on the fixed copy fails with the repo-config sentence. The new test fails on `0df7d3d`. Both suite runs are 42 OK. Unmarked `today --json` matches `0df7d3d`.
- 2026-11-03T18:06:43+08:00 — Live checkout fingerprint matches the start.
- 2026-11-03T18:07:48+08:00 — Commit `bba597d`. `main` is still `0df7d3d`.
- 2026-11-03T18:08:39+08:00 — `git branch -vv` shows `tepi-test-config-gap` at `bba597d` with no upstream. `git worktree list` shows this worktree and `/tmp/tepi-catchup-fix`. Commit this note. Do not merge, push, rescan, or open the real log.
