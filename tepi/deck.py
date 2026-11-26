import json
import re
from dataclasses import dataclass, replace
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
    sentence_gloss: str = ""
    cloze: str | None = None
    note: str | None = None


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
    catch_up: bool = False
    catch_up_review_cap: int = 0


def _read_deck(path: Path) -> Deck:
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
                sentence_gloss=_optional_text(item, "sentenceGloss", index) or "",
                cloze=_optional_text(item, "cloze", index),
                note=_optional_text(item, "note", index),
            )
        )
        seen[word_id] = index
    for entry in entries:
        for req in entry.requires:
            earlier = seen.get(req)
            if earlier is not None and earlier >= entry.index:
                raise TepiError(f"{entry.id} requires {req}, which is not earlier in the deck.")
    return Deck(tuple(entries))


def load_deck(path: Path) -> Deck:
    """Load one deck file.

    A require must name an earlier word in this file, or a word in an earlier
    deck file in the same directory. `words.json` is earlier than `words-2.json`.
    """
    path = Path(path)
    deck = _read_deck(path)
    known = _earlier_ids(path)
    known.update(entry.id for entry in deck.entries)
    for entry in deck.entries:
        for req in entry.requires:
            if req not in known:
                raise TepiError(
                    f"{path.name}: {entry.id} requires {req}, which is not in the deck."
                )
    return deck


def _earlier_ids(path: Path) -> set[str]:
    match = _DECK_FILE.match(path.name)
    if match is None:
        return set()
    number = int(match.group(1)) if match.group(1) else 0
    earlier: list[tuple[int, str, Path]] = []
    try:
        names = list(path.parent.iterdir())
    except OSError as err:
        raise TepiError(f"Could not read the deck directory {path.parent}.") from err
    for sibling in names:
        if not sibling.is_file() or sibling.resolve() == path.resolve():
            continue
        sibling_match = _DECK_FILE.match(sibling.name)
        if sibling_match is None:
            continue
        sibling_number = int(sibling_match.group(1)) if sibling_match.group(1) else 0
        if sibling_number < number:
            earlier.append((sibling_number, sibling.name, sibling))
    earlier.sort()
    found: set[str] = set()
    for _, _, sibling in earlier:
        for entry in _read_deck(sibling).entries:
            found.add(entry.id)
    return found


# words.json, then words-2.json, words-3.json, and so on.
_DECK_FILE = re.compile(r"^words(?:-([1-9]\d*))?\.json$")


def deck_paths(directory: Path) -> tuple[Path, ...]:
    """Deck files in teaching order.

    `words.json` is first. `words-N.json` follows by N, so `words-2.json`
    comes before `words-10.json`. `words.schema.json` is not a deck.
    """
    directory = Path(directory)
    numbered: list[tuple[int, str, Path]] = []
    try:
        names = list(directory.iterdir())
    except OSError as err:
        raise TepiError(f"Could not read the deck directory {directory}.") from err
    for path in names:
        match = _DECK_FILE.match(path.name)
        if match is None or not path.is_file():
            continue
        number = int(match.group(1)) if match.group(1) else 0
        numbered.append((number, path.name, path))
    numbered.sort()
    if not numbered or numbered[0][0] != 0:
        raise TepiError(f"The deck directory {directory} has no words.json.")
    return tuple(path for _, _, path in numbered)


def load_decks(paths) -> Deck:
    """Load deck files in the order given and number the words from the start."""
    parts: list[tuple[Path, Deck]] = []
    located: dict[str, int] = {}
    for path in paths:
        path = Path(path)
        part = _read_deck(path)
        for entry in part.entries:
            if entry.id in located:
                raise TepiError(f"The decks repeat the id {entry.id!r}.")
            located[entry.id] = len(located)
        parts.append((path, part))
    combined: list[Entry] = []
    for path, part in parts:
        for entry in part.entries:
            for req in entry.requires:
                if req not in located:
                    raise TepiError(
                        f"{path.name}: {entry.id} requires {req}, which is not in the decks."
                    )
                if located[req] >= located[entry.id]:
                    raise TepiError(f"{entry.id} requires {req}, which is not earlier in the decks.")
            combined.append(replace(entry, index=len(combined)))
    return Deck(tuple(combined))


def load_curriculum(root: Path) -> Deck:
    """Load every deck under `root/deck` in teaching order."""
    return load_decks(deck_paths(Path(root) / "deck"))


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
    review_cap = _count(raw, "reviewCap")
    if "catchUpReviewCap" in raw:
        catch_up_review_cap = _count(raw, "catchUpReviewCap")
        if catch_up_review_cap < review_cap:
            raise TepiError("catchUpReviewCap must be at least reviewCap.")
    else:
        catch_up_review_cap = review_cap
    return Config(
        new_per_day=_count(raw, "newPerDay"),
        review_cap=review_cap,
        known_intervals=tuple(intervals),
        fuzzy_days=_days(raw, "fuzzyDays"),
        missed_days=_days(raw, "missedDays"),
        catch_up=_flag(raw, "catchUp"),
        catch_up_review_cap=catch_up_review_cap,
    )


def _text(item: dict, key: str, index: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        label = item.get("id") or f"word {index + 1}"
        raise TepiError(f"{label} is missing {key}.")
    return value


def _optional_text(item: dict, key: str, index: int) -> str | None:
    if key not in item or item[key] is None:
        return None
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        label = item.get("id") or f"word {index + 1}"
        raise TepiError(f"{label} has an invalid {key}.")
    return value


def _count(raw: dict, key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value < 0:
        raise TepiError(f"{key} must be a number of words, zero or more.")
    return value


def _flag(raw: dict, key: str) -> bool:
    if key not in raw:
        return False
    value = raw[key]
    if not isinstance(value, bool):
        raise TepiError(f"{key} must be true or false.")
    return value


def _days(raw: dict, key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or value < 1:
        raise TepiError(f"{key} must be at least 1 day.")
    return value
