# Tepi

A Bahasa Melayu edge chip for this Omarchy laptop. One quiet word on the bar, two new words a day, and a log of what has already been learned.

Peninsular Malaysia, standard Malaysian spelling. No audio.

## Layout

| Path | What it is |
| --- | --- |
| `deck/words.json` | The curriculum. Order in the array is teaching order. |
| `deck/words.schema.json` | The deck contract. |
| `config.json` | Daily caps and the recall ladder. |
| `tepi/` | The `tepi` command. |
| `plugin/` | The `manny.tepi` bar widget. Linked from `~/.config/omarchy/plugins/manny.tepi`. |
| `~/.local/share/tepi/tepi.sqlite` | Progress. Created on the first real day, never committed. |

The vault note at `Tepi/Tepi.md` in the Obsidian vault is the resume page. This repo wins if the two disagree.

## A word

```json
{
  "id": "air",
  "lemma": "air",
  "root": "air",
  "gloss": "water",
  "sentence": "Saya mahu air.",
  "register": "neutral",
  "requires": ["saya", "mahu"]
}
```

- `id` is stable. It does not change when the gloss is edited.
- `lemma` is the form the chip shows.
- `root` groups cousins (`minum`, `minuman`) without teaching them as one entry.
- `sentence` uses this word and words already in the deck.
- `requires` lists those earlier ids. A word can be introduced only after each of them has been introduced.
- `register` is `neutral`, `casual`, or `formal`. The first words stay `neutral` (`saya`, `mahu`, `tidak`, `sudah`).

`id` values are unique. Every id in `requires` appears earlier in `words`.

## What one day does

The command builds a day plan once, in the local timezone, and keeps it stable until the next day.

1. Reviews come first: words due today or earlier, oldest due date first, up to `reviewCap` (4).
2. Then new words, in deck order, up to `newPerDay` (2). A word is skipped until everything in `requires` has been introduced.
3. The chip shows one word. An unrated review in today's plan comes before a new word. After both are done, the chip rests on the latest word introduced today.

Ratings:

| Rating | Schedule |
| --- | --- |
| `known` | Due after `knownIntervals[index]` days (1, 3, 7, 16, 30), then the index advances. A `known` rating after the last step settles the word. |
| `fuzzy` | The index stays. Due again in `fuzzyDays` (2). |
| `missed` | The index returns to 0. Due again in `missedDays` (1). |

A new word is due the next day, at index 0, before any rating. Revealing the gloss is a glance. Only a rating moves the schedule. The `known` rating that comes after the 30-day gap settles the word. Settled words stay in the log and leave the daily cap.

## Command

`tepi` is on the path via `~/.local/bin/tepi`. The first run of a local day writes that day's plan into `~/.local/share/tepi/tepi.sqlite` and that is what introduces the new words.

```
tepi today
tepi reveal
tepi rate known
tepi rate fuzzy
tepi rate missed
tepi log
```

`today` shows one word and hides the gloss on a new word or a review. `reveal` shows the meaning. `rate` is for a review, and it shows the meaning either way. A new word waits until tomorrow. `log` lists settled words, words still in play, and the last seven days. `log --all` prints the whole diary.

`today --json`, `reveal --json`, `rate known --json`, and `log --json` print the same facts for the bar chip.

`TEPI_DATA_DIR` and `TEPI_TODAY` override the log location and the date. The tests use them.

```
python3 -m unittest discover -s tests
```

## Chip

The widget in `plugin/` is linked into `~/.config/omarchy/plugins/manny.tepi` and sits on the left of the bar, after the workspaces.

It shows the lemma. Rest is dimmer. A click opens the meaning and the sentence. A review offers Known, Fuzzy, and Missed, and the card stays open afterward with the meaning and the next due date.

The widget calls `tepi today --json` when it appears and about once a minute. The command decides the schedule. The first time the chip loads, that call starts the deck.

After an edit in this repo, run `omarchy-shell shell rescanPlugins`. The shell watches the plugin directory, and the install there is a link.

## First deck

`deck/words.json` holds 71 neutral words, one morning in teaching order. At two new words a day that is about five weeks before any later chapter.

The arc runs from `Selamat pagi` through breakfast, the time of day, getting ready, the office, and the laptop on the desk. Sentences stay inside words already listed. `tidak` is the not that stands before a verb. `bukan` is the not that stands before a noun. Tomorrow is `esok`. `semalam` is yesterday, and in Peninsular speech it can also mean last night. Email is `e-mel`. The laptop is `komputer riba`. Verbs are the plain form (`baca`, `minum`), which is how they sound after `mahu` and `sudah`.

`Apa khabar?` is the how-are-you greeting. The gloss of `khabar` stays "news", which is what the word itself means.

## Build order

1. First morning words in `deck/words.json`. Done.
2. The `tepi` command: introduce, rate, log. Done.
3. The `manny.tepi` bar widget. Done. Source in `plugin/`, linked into the shell.
4. After the log has real days in it: root cousins, a sentence built only from settled words, and a prompt that follows the workspace.

## Status

The chip is on the bar. It shows one lemma. A click reveals the meaning, and a review can be rated from the card. The first time the chip loads, it runs `tepi today` and that starts the deck.
