# Tepi catch-up

Piece 1 of 2. Branch `tepi-catchup`. Stopped after the real progress file changed.

There is no `master` branch. `main` is still `197a09a`. Nothing was pushed.

## 1. Files changed

Code commit `c8adb755dad419c61c0e120f868ac6230d3df709` — Add a catch-up review cap that drops back to reviewCap on its own.

| File | What |
| --- | --- |
| `config.json` | `catchUpReviewCap` 12, `catchUp` true |
| `tepi/deck.py` | Load and check the two keys. Missing keys leave catch-up off. |
| `tepi/engine.py` | Pick the cap when a day is first planned. Keep a stored plan as it is. |
| `tepi/db.py` | Add `plans.catch_up`. Leave `user_version` at 1. |
| `tepi/cli.py` | `catchUp` on `today --json`. ` (catch-up)` on the text heading. |
| `README.md` | The review line now describes catch-up. |
| `tests/test_catchup.py` | The new tests. |

This report is the commit after that one, on `tepi-catchup`.

## 2. What changed

- While `catchUp` is true and at least one review is due before today, a new day's plan takes up to `catchUpReviewCap` (12). Due today does not raise the cap.
- With nothing overdue, or with `catchUp` false, the cap is `reviewCap` (4).
- The choice is made in `ensure_plan` and stored on that day's plan. A later call the same day returns the stored plan.
- The command does not write `config.json`. Turning catch-up off is the one key `"catchUp": false`.
- A missing `catchUp` is false. A missing `catchUpReviewCap` equals `reviewCap`. Old configs keep the old cap.
- `catchUpReviewCap` uses the same whole-number check as `reviewCap`. Below `reviewCap` raises `TepiError`. `catchUp` must be a boolean.
- `today --json` adds `"catchUp": true` or `false`. The text heading gains ` (catch-up)` after the count when that day was planned under the higher cap, for example `1/12 (catch-up)`.
- `user_version` stays 1. The new column defaults to 0, so the previous command can still open the log and still insert a plan.

## 3. Tests

Before this change, on `197a09a`:

```
Ran 29 tests in 0.259s
OK
```

After, on `tepi-catchup`:

```
Ran 37 tests in 0.459s
OK
```

The eight new tests are in `tests/test_catchup.py`. The six the brief asked for are the first six below. `known` is the rating used for "good".

Fail-on-old: a detached worktree at `197a09a` in `/tmp/tepi-197a09a`, with `PYTHONPATH` set there. `tepi.engine.__file__` was `/tmp/tepi-197a09a/tepi/engine.py`. Every new test failed. The worktree was removed. `TEPI_DATA_DIR` in those tests was a temp folder.

```
test_a_bad_catch_up_cap_raises_the_same_error_as_a_bad_review_cap ... FAIL
test_a_config_without_the_new_keys_uses_the_review_cap ... ERROR
test_an_existing_plan_is_not_rebuilt ... ERROR
test_catch_up_false_keeps_the_review_cap ... ERROR
test_due_today_stays_on_the_review_cap_while_catch_up_is_true ... ERROR
test_known_days_clear_the_backlog_and_leave_config_untouched ... FAIL
test_overdue_reviews_use_the_catch_up_cap ... FAIL
test_today_command_marks_catch_up_and_log_stays_plain ... ERROR

ERROR: test_a_config_without_the_new_keys_uses_the_review_cap
AttributeError: 'Config' object has no attribute 'catch_up'

ERROR: test_an_existing_plan_is_not_rebuilt
AttributeError: 'Plan' object has no attribute 'catch_up'

ERROR: test_catch_up_false_keeps_the_review_cap
AttributeError: 'Plan' object has no attribute 'catch_up'

ERROR: test_due_today_stays_on_the_review_cap_while_catch_up_is_true
AttributeError: 'Plan' object has no attribute 'catch_up'

ERROR: test_today_command_marks_catch_up_and_log_stays_plain
KeyError: 'catchUp'

FAIL: test_a_bad_catch_up_cap_raises_the_same_error_as_a_bad_review_cap
AssertionError: TepiError not raised

FAIL: test_known_days_clear_the_backlog_and_leave_config_untouched
AssertionError: 4 not greater than 4

FAIL: test_overdue_reviews_use_the_catch_up_cap
AssertionError: 4 != 12

Ran 8 tests in 0.064s
FAILED (failures=3, errors=5)
```

On the old command, 20 overdue reviews produce 4, not 12. A bad `catchUpReviewCap` is ignored, so no `TepiError`. The multi-day run never rises above 4. The false, due-today, and old-config cases then die on the missing `catch_up` field. Their count, where the test reached it, was already 4.

## 4. The real database

Read at the start of the session, before any edit:

```
89746d1de20a08a6e49e7ba42e735b972dc2e51f9dbe64db72c33c85d8f16608
2026-11-03 00:07:37.633087822 +0800
61440 bytes
```

Read again at 2026-11-03T17:05:31+08:00, after the copy commands below, and unchanged from 16:59:39:

```
acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151
2026-11-03 16:59:39.243280254 +0800
61440 bytes
```

The file is not byte-identical. I did not run `tepi` against it. `~/.local/bin/tepi` is `/home/manny/Work/tepi/bin/tepi`, so the bar runs this working tree. `plugin/BarWidget.qml` calls `today --json` about once a minute and does not set `TEPI_DATA_DIR`. The mtime 16:59:39 is during the test window, after `connect()` had learned to add `plans.catch_up`.

A copy made after that mtime shows the column, `user_version` still 1, 36 plans, 71 progress rows, 49 overdue, and no event with `ts >= 2026-11-03T16:00:00`. Today's stored plan is still:

```
reviews ["lapar", "ya", "di", "perlu"]
introduced ["tadi"]
catch_up 0
```

Those four review ids match the copy read at the start. The first read did not select `introduced`. Nothing in this session inserted `tadi`: progress was already 71, and there is no event after 16:00. I did not reverse the column. That would be another write.

## 5. `tepi today --json` on a copy

`TEPI_DATA_DIR` was a temp folder. `TEPI_TODAY=2026-11-03`. The copy was deleted afterward. The original hash stayed `acfd6f6f…` across this command.

```json
{
  "date": "2026-11-03",
  "mode": "rest",
  "revealed": true,
  "word": {
    "id": "tadi",
    "lemma": "tadi",
    "root": "tadi",
    "register": "neutral",
    "gloss": "earlier",
    "sentence": "Saya minum kopi tadi."
  },
  "plan": {
    "reviews": ["lapar", "ya", "di", "perlu"],
    "new": ["tadi"]
  },
  "remaining": {"reviews": 0, "new": 0},
  "catchUp": false
}
```

Review count: 4. `catchUp`: false. Today already had a plan, and that plan is finished.

Same copy, not the required command, `TEPI_TODAY=2026-11-04`. This writes only the copy. It shows the higher cap on the real backlog for a day that has no plan yet:

```json
{
  "date": "2026-11-04",
  "mode": "review",
  "revealed": false,
  "word": {
    "id": "penat",
    "lemma": "penat",
    "root": "penat",
    "register": "neutral",
    "gloss": null,
    "sentence": null
  },
  "plan": {
    "reviews": [
      "penat", "belum", "awak", "pergi", "kerja", "sibuk",
      "meja", "dahaga", "tolong", "terima-kasih", "pejabat", "duduk"
    ],
    "new": []
  },
  "remaining": {"reviews": 12, "new": 0},
  "catchUp": true
}
```

Review count: 12. `catchUp`: true.

The bar is running this working tree now. The first plan for 2026-11-04 will use the higher cap if this checkout is still in place.

## 6. Widget check

File: `plugin/BarWidget.qml`. The bar's copy is that file. `readlink -f ~/.config/omarchy/plugins/manny.tepi/BarWidget.qml` prints `/home/manny/Work/tepi/plugin/BarWidget.qml`.

Line 151 is `payload = JSON.parse(text)`. Lines 162–164, for `today`, keep that object when it has a lemma or `mode === "empty"`. Nothing walks a fixed set of keys. `catchUp` is not read. `mode`, `word.lemma`, and `revealed` are. An extra key does not break that parse. The widget file was not edited. No rescan was run.

## 7. What must be true

1. PASS. Overdue reviews plan up to 12. Nothing overdue plans up to 4. Proof: `test_overdue_reviews_use_the_catch_up_cap` and `test_due_today_stays_on_the_review_cap_while_catch_up_is_true`.
2. PASS at code level. `test_known_days_clear_the_backlog_and_leave_config_untouched` rates `known` until a day has nothing overdue, that day's plan is at most 4, and `config.json`'s sha256 is unchanged. No code path writes `config.json`.
3. PASS. `test_catch_up_false_keeps_the_review_cap` plans 4 of 20 overdue. `test_a_config_without_the_new_keys_uses_the_review_cap` does the same when the keys are absent.
4. FAIL. The required command, `TEPI_TODAY=2026-11-03` on a copy, shows 4 reviews and `catchUp` false. Today's plan was already stored. The 2026-11-04 command on that same copy shows 12 and `catchUp` true. That was not the required date.
5. FAIL. `~/.local/share/tepi/tepi.sqlite` changed. sha256 `89746d1d…` at 2026-11-03 00:07:37 became `acfd6f6f…` at 2026-11-03 16:59:39. See section 4.
6. PASS, with one naming note. The suite is 37 OK. `git log main -1` is `197a09a`. `git rev-parse master` fails: there is no `master`. `tepi-catchup` has no upstream. Nothing was pushed. This report's commit is the tip after `c8adb75`.

## 8. Waiting on Christian

Merging `tepi-catchup` into `main`. Say so in chat before that. Do not push until then.

Also in the way: the real log already has the `catch_up` column, and the bar is running this checkout. Say if you want the working tree back on `main` so tomorrow's plan stays at 4 until you take the branch.

## 9. Decision log (MYT)

- Before 2026-11-03T16:57:10+08:00 — Record the real log's sha256 and mtime before any edit. Inspect only a copy. Today's plan already lists `lapar`, `ya`, `di`, `perlu`. Do not rebuild a stored plan.
- 2026-11-03T16:57:10+08:00 — Branch `tepi-catchup` from `197a09a`. Overdue means due before today. The cap is chosen once, inside `ensure_plan`. `"good"` in the brief is the rating `known`.
- 2026-11-03T16:57:10+08:00 — Missing `catchUp` is false. Missing `catchUpReviewCap` equals `reviewCap`. The text marker sits on the heading: `1/12 (catch-up)`. `user_version` stays 1 so the previous command still opens the log.
- 2026-11-03T16:59:39+08:00 — The real log's mtime moves. Later reads show `plans.catch_up` added and today's reviews unchanged. No event after 16:00. Do not write the file again to undo the column.
- 2026-11-03T17:02:36+08:00 — The hash no longer matches the session start. Stop feature work. The copy's `today` for 2026-11-03 is the required evidence and shows `catchUp` false. The same copy on 2026-11-04 shows 12 and `catchUp` true, then the copy is deleted.
- 2026-11-03T17:05:31+08:00 — The real log's hash is still `acfd6f6ff8977bfeaa0628119780418307e5f31be077d42180e4dffb10fdb151`. Commit the code and this note. Do not merge, push, rescan, or open the original log.

## Stop

Stopped because the real `~/.local/share/tepi/tepi.sqlite` was written. Evidence is in section 4. No portal commands, no sudo, no install, no push, no merge, no timer, no restart, no `omarchy-shell`.
