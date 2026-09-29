# Tepi

A Bahasa Melayu edge chip for this Omarchy laptop. One quiet word on the bar, two new words a day, and a log of what has already been learned.

Peninsular Malaysia, standard Malaysian spelling. No audio.

## Layout

| Path | What it is |
| --- | --- |
| `deck/words.json` | The curriculum. Order in the array is teaching order. |
| `deck/words.schema.json` | The deck contract. |
| `config.json` | Daily caps and the recall ladder. |
| `~/.local/share/tepi/tepi.sqlite` | Progress. Created by the command, never committed. |

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

A new word is due the next day, at index 0, before any rating. Revealing the gloss is a glance. Only a rating moves the schedule. Settled words stay in the log and leave the daily cap.

## Build order

1. Fill `deck/words.json` with the first morning words.
2. Add the `tepi` command that introduces a word, records a rating, and prints the log.
3. Add the `manny.tepi` bar widget. Its source will live in this repo and be linked from `~/.config/omarchy/plugins/manny.tepi/`.
4. After the log has real days in it: root cousins, a sentence built only from settled words, and a prompt that follows the workspace.

## Status

Scaffold only. The deck is empty. There is no command and no chip yet.
