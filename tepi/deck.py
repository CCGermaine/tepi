import json
from dataclasses import dataclass
from pathlib import Path


class TepiError(Exception):
    """A problem the command should print and stop on."""


@dataclass(frozen=True)
class Entry:
    id: str
    lemma: str
    root: str
    gloss: str
    sentence: str
    register: str
    requires: tuple[str, ...]
    index: int


@dataclass(frozen=True)
class Deck:
    entries: tuple[Entry, ...]

    @property
    def by_id(self) -> dict[str, Entry]:
        return {entry.id: entry for entry in self.entries}

    def entry(self, word_id: str) -> Entry:
        try:
            return self.by_id[word_id]
        except KeyError as err:
            raise TepiError(f"The deck has no word {word_id!r}.") from err


@dataclass(frozen=True)
class Config:
    new_per_day: int
    review_cap: int
    known_intervals: tuple[int, ...]
    fuzzy_days: int
    missed_days: int


def load_deck(path: Path) -> Deck:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the deck at {path}.") from err
    words = raw.get("words")
    if not isinstance(words, list):
        raise TepiError(f"The deck at {path} has no word list.")
    entries: list[Entry] = []
    seen: dict[str, int] = {}
    for index, item in enumerate(words):
        if not isinstance(item, dict):
            raise TepiError(f"Word {index + 1} in the deck is not an object.")
        word_id = _text(item, "id", index)
        if word_id in seen:
            raise TepiError(f"The deck repeats the id {word_id!r}.")
        requires = item.get("requires", [])
        if not isinstance(requires, list) or not all(isinstance(req, str) and req for req in requires):
            raise TepiError(f"{word_id} has a requires list Tepi cannot read.")
        for req in requires:
            if req not in seen:
                raise TepiError(f"{word_id} requires {req}, which is not earlier in the deck.")
        entries.append(
            Entry(
                id=word_id,
                lemma=_text(item, "lemma", index),
                root=_text(item, "root", index),
                gloss=_text(item, "gloss", index),
                sentence=_text(item, "sentence", index),
                register=_text(item, "register", index),
                requires=tuple(requires),
                index=index,
            )
        )
        seen[word_id] = index
    return Deck(tuple(entries))


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise TepiError(f"Could not read the schedule at {path}.") from err
    intervals = raw.get("knownIntervals")
    if (
        not isinstance(intervals, list)
        or not intervals
        or not all(isinstance(day, int) and day > 0 for day in intervals)
    ):
        raise TepiError("knownIntervals must be a list of days.")
    return Config(
        new_per_day=_count(raw, "newPerDay"),
        review_cap=_count(raw, "reviewCap"),
        known_intervals=tuple(intervals),
        fuzzy_days=_days(raw, "fuzzyDays"),
        missed_days=_days(raw, "missedDays"),
    )


def _text(item: dict, key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        label = item.get("id") or f"word {index + 1}"
        raise TepiError(f"{label} is missing {key}.")
    return value


def _count(raw: dict, key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value < 0:
        raise TepiError(f"{key} must be a number of words, zero or more.")
    return value


def _days(raw: dict, key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value < 1:
        raise TepiError(f"{key} must be at least 1 day.")
    return value
