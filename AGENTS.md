# AGENTS.md

Tepi: a Bahasa Melayu learning chip for the Omarchy bar. The `tepi` command (Python, stdlib) schedules two new words a day plus reviews, and the `manny.tepi` QML widget shows one word. Peninsular Malaysian spelling, no audio. See README.md.

## Layout

- `deck/words.json` the curriculum, array order is teaching order. Contract: `deck/words.schema.json`.
- `deck/kamus.json`, `deck/tesaurus.json` results of the last dictionary and thesaurus checks.
- `config.json` daily caps and the recall ladder.
- `tepi/` the command, `bin/tepi` its launcher (linked from `~/.local/bin/tepi`).
- `plugin/` the bar widget, linked from `~/.config/omarchy/plugins/manny.tepi`.
- Progress lives in `~/.local/share/tepi/tepi.sqlite`. It is real user data and never committed.

## Run and test

```sh
python3 -m unittest discover -s tests
python3 -m tepi today            # or: tepi today --json
```

Tests and manual runs must set `TEPI_DATA_DIR` to a temp folder (and `TEPI_TODAY` for a fixed date) so they never touch the real progress log. After a widget edit, Christian runs `omarchy-shell shell rescanPlugins`.

## Hard rules

1. Never push to main or master, never force-push, and never deploy, enable timers, or restart services without Christian's explicit yes in chat.
2. Never print, log, or commit secrets or tokens. `.env` and `discord.env` stay untracked.
3. Never write to, reset, or delete `~/.local/share/tepi/tepi.sqlite`. Never commit `*.sqlite`.
4. `tepi check` and `tepi thesaurus --deck` hit the DBP portals and rewrite deck files. Run them only when asked, and never store definitions, citations, or Jawi from the portal, only the status and word class.
5. Deck edits keep `id` stable, keep every `requires` id earlier in the array, and keep the first words `neutral`. Do not invent glosses or spellings without the dictionary check.
6. Run `python3 -m unittest discover -s tests` before reporting done. If a `_handoff/reports/` folder exists, write the report there.
7. Bug-to-lint-rule: when the same bug or mistake shows up a second time, add an automatic check (lint rule, test, or guard script) that fails on it, rather than a note. Show that the check fails on the old code.
8. Keep changes small, one feature per build. No new dependencies.
9. Builds work in a git worktree under /tmp, never in ~/Work/tepi. The bar widget runs the live checkout against the real database every 60 seconds.
